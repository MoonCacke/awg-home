# AmneziaWG: установка и настройка

## 1. Подготовка Linux

Для Debian/Ubuntu используйте актуальную официальную инструкцию установки
модуля AmneziaWG. После установки обязательно проверьте модуль для **текущего**
ядра:

```bash
uname -r
modinfo amneziawg
command -v awg
command -v awg-quick
```

Если `modinfo` сообщает, что модуль отсутствует, не запускайте интерфейс:
сначала установите заголовки текущего ядра и пересоберите DKMS-модуль.

## 2. Ключи

Создавайте ключи с закрытой маской доступа:

```bash
umask 077
awg genkey | tee server.key | awg pubkey > server.pub
awg genkey | tee client-01.key | awg pubkey > client-01.pub
```

Файлы `*.key` нельзя передавать в Git. Для каждого устройства нужна отдельная
пара ключей и отдельный адрес `/32`.

## 3. Конфигурация сервера

Возьмите [`../examples/awg-server.conf.example`](../examples/awg-server.conf.example),
подставьте ключи и сохраните как `/etc/amnezia/amneziawg/awg0.conf` с правами
`0600`.

Параметры маскировки `Jc`, `Jmin`, `Jmax`, `S1`, `S2`, `H1`–`H4` должны быть
согласованы между сервером и клиентом. Надёжнее экспортировать их из профиля,
созданного актуальной версией AmneziaVPN, чем придумывать вручную.

Разрешите маршрутизацию IPv4:

```bash
sudo sysctl -w net.ipv4.ip_forward=1
```

Для постоянной настройки создайте отдельный файл в `/etc/sysctl.d/`, не
редактируя чужие параметры. Затем настройте firewall и NAT по примеру
[`../examples/awg-nftables.nft.example`](../examples/awg-nftables.nft.example).

Проверьте конфигурацию и запустите интерфейс:

```bash
sudo awg-quick strip awg0 >/dev/null
sudo systemctl enable --now awg-quick@awg0
sudo systemctl status awg-quick@awg0 --no-pager
sudo awg show awg0
```

## 4. Роутер перед HOME

Если сервер находится за домашним роутером:

1. закрепите за HOME постоянный LAN-адрес;
2. перенаправьте выбранный внешний UDP-порт на тот же порт HOME;
3. разрешите этот UDP-порт в firewall HOME;
4. задайте клиенту `PersistentKeepalive = 25`;
5. проверьте отсутствие CGNAT у домашнего провайдера.

При CGNAT входящее перенаправление портов не работает. Используйте VPS как
публичную точку входа или постоянный исходящий uplink HOME → VPS.

## 5. Клиент

Используйте [`../examples/awg-client.conf.example`](../examples/awg-client.conf.example).
`AllowedIPs = 0.0.0.0/0` создаёт полный IPv4-туннель. Для доступа только к
домашним подсетям перечислите только их.

Один файл профиля нельзя одновременно включать на двух устройствах: endpoint
peer будет постоянно переключаться между ними. Создавайте отдельный peer.

## 6. Добавление peer без остановки сервера

Сначала сохраните резервную копию постоянного конфига:

```bash
sudo cp -a /etc/amnezia/amneziawg/awg0.conf \
  /etc/amnezia/amneziawg/awg0.conf.before-client-$(date -u +%Y%m%dT%H%M%SZ)
```

Добавьте блок `[Peer]` в постоянный файл, затем примените тот же peer в рантайме:

```bash
sudo awg set awg0 peer '<CLIENT_PUBLIC_KEY>' allowed-ips 10.66.0.2/32
sudo awg show awg0 allowed-ips
```

Так действующие пользователи не теряют соединение. Перед перезагрузкой убедитесь,
что рабочая и постоянная конфигурации содержат одинаковый peer.

## 7. Проверка

```bash
sudo systemctl is-active awg-quick@awg0
sudo ss -lunp | grep '<AWG_PORT>'
sudo awg show awg0
ip -4 route
sudo nft list ruleset
```

Успешное рукопожатие ещё не доказывает доступ в интернет. Отдельно проверяйте
форвардинг, NAT, DNS и обратный маршрут.
