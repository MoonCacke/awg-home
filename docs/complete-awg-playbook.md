# Полное развёртывание AmneziaWG

Руководство рассчитано на Debian/Ubuntu и два варианта:

1. публичный AWG-сервер на VPS;
2. HOME за роутером, принимающий клиентов через port forwarding или постоянный
   uplink к VPS.

Команды нельзя выполнять вслепую. Сначала замените все `<PLACEHOLDER>` и
проверьте имена интерфейсов. Установка пакетов, перезапуск служб и изменение
firewall требуют отдельного согласования с владельцем сервера.

## 0. Карта параметров

До изменений заполните локально:

| Параметр | Пример документации |
|---|---|
| Сервер | `HOME` или `VPS-OUT` |
| WAN-интерфейс | `<WAN_IF>` |
| AWG-интерфейс | `awg0` |
| UDP-порт | `<AWG_PORT>` |
| VPN-подсеть | `10.66.0.0/24` |
| Адрес сервера | `10.66.0.1/24` |
| Первый клиент | `10.66.0.2/32` |
| Публичный endpoint | `<SERVER_IP_OR_NAME>:<AWG_PORT>` |

Проверьте пересечения:

```bash
ip -br address
ip -4 route
ip -4 rule
sudo nft list ruleset
sudo ss -lunp
```

Не используйте VPN-подсеть, уже занятую LAN, Docker, UTM/VM, Tailscale или
другим туннелем.

## 1. Зафиксировать исходное состояние

```bash
date -u
hostnamectl
uname -r
ip -br address
ip -4 route
ip -4 rule
sudo systemctl --failed
sudo nft list ruleset
```

Сохраните вывод в рабочие заметки, но не публикуйте ключи. Если AWG уже
установлен:

```bash
sudo awg show
sudo systemctl status 'awg-quick@*' --no-pager
```

## 2. Установить AmneziaWG

Следуйте актуальной инструкции Amnezia для вашей версии Debian/Ubuntu:

<https://docs.amnezia.org/documentation/instructions/install-amneziawg-kernel-module-linux/>

После получения разрешения владельца установите необходимые заголовки ядра и
пакет AmneziaWG. Затем проверьте:

```bash
uname -r
modinfo amneziawg
command -v awg
command -v awg-quick
```

`modinfo amneziawg` должен показывать модуль именно для работающего ядра.
Если пакет установил новое ядро, не перезагружайтесь, пока не подтверждено
наличие модуля для нового ядра.

## 3. Создать ключи

На сервере:

```bash
umask 077
awg genkey | tee server.key | awg pubkey > server.pub
```

Для каждого устройства создайте отдельную пару:

```bash
umask 077
awg genkey | tee client-01.key | awg pubkey > client-01.pub
```

Требования:

- один private key — только на одном устройстве;
- каждому peer назначается уникальный `/32`;
- private key, заполненный `.conf` и QR-код не отправляются в Git или чат;
- публичный ключ можно передавать серверу, но лучше не публиковать открыто.

## 4. Подготовить серверный конфиг

Скопируйте
[`../examples/awg-server.conf.example`](../examples/awg-server.conf.example)
в закрытое место и заполните значения. Рабочий путь обычно:

```text
/etc/amnezia/amneziawg/awg0.conf
```

Права:

```bash
sudo chown root:root /etc/amnezia/amneziawg/awg0.conf
sudo chmod 600 /etc/amnezia/amneziawg/awg0.conf
```

Параметры `Jc`, `Jmin`, `Jmax`, `S1`, `S2`, `H1`–`H4` должны соответствовать
клиентскому профилю. Практичный путь — экспортировать рабочий профиль из
актуальной AmneziaVPN и перенести значения без изменения.

Проверка синтаксиса без поднятия интерфейса:

```bash
sudo awg-quick strip /etc/amnezia/amneziawg/awg0.conf >/dev/null
```

## 5. Включить маршрутизацию

Временно для теста:

```bash
sudo sysctl -w net.ipv4.ip_forward=1
```

После успешного теста создайте отдельный файл, например
`/etc/sysctl.d/90-awg-forward.conf`, содержащий:

```text
net.ipv4.ip_forward=1
```

Не перезаписывайте целиком `/etc/sysctl.conf`.

## 6. Настроить firewall и NAT

Сначала определите реальный WAN-интерфейс:

```bash
ip route show default
```

Возьмите
[`../examples/awg-nftables.nft.example`](../examples/awg-nftables.nft.example),
замените `eth0`, `awg0` и подсеть. Проверьте файл до загрузки:

```bash
sudo nft --check --file <AWG_NFT_FILE>
```

Правила должны:

- принимать только VPN-источник из назначенной подсети;
- разрешать `established,related` обратно;
- выполнять masquerade/SNAT только на нужном WAN;
- не открывать VPN-клиентам всю домашнюю LAN без явного решения;
- не менять существующие таблицы сайта, SSH, OpenClaw и других VPN.

После отдельного разрешения загрузите правила и убедитесь, что счётчики
растут. Постоянную загрузку оформляйте отдельной systemd-службой или include в
существующем nftables, а не случайной командой из shell history.

## 7. Запустить интерфейс

Перед запуском проверьте, что порт свободен:

```bash
sudo ss -lunp | grep ':<AWG_PORT>' || true
```

После разрешения владельца:

```bash
sudo systemctl enable --now awg-quick@awg0
sudo systemctl status awg-quick@awg0 --no-pager
sudo awg show awg0
ip -br address show awg0
```

## 8. Настроить роутер

Для HOME за роутером:

1. закрепите LAN-IP HOME через DHCP reservation;
2. создайте правило `<AWG_PORT>/UDP → <HOME_LAN_IP>:<AWG_PORT>`;
3. не создавайте правило TCP для AWG;
4. проверьте, что WAN-адрес роутера не относится к `10.0.0.0/8`,
   `172.16.0.0/12`, `192.168.0.0/16` или `100.64.0.0/10`;
5. при CGNAT используйте VPS relay/uplink — обычный port forward не поможет.

## 9. Создать клиентский профиль

Заполните
[`../examples/awg-client.conf.example`](../examples/awg-client.conf.example).

Полный IPv4-туннель:

```ini
AllowedIPs = 0.0.0.0/0
```

Только доступ к HOME:

```ini
AllowedIPs = 10.66.0.0/24, 192.168.50.0/24
```

Для клиента за NAT оставьте:

```ini
PersistentKeepalive = 25
```

IPv6 либо настраивается полностью на обеих сторонах, либо явно блокируется.
Нельзя оставлять IPv6 «мимо» туннеля, если ожидается полный VPN.

## 10. Проверить соединение

На сервере:

```bash
sudo awg show awg0
sudo journalctl -u awg-quick@awg0 -n 50 --no-pager
sudo nft list ruleset
```

На клиенте проверяйте по порядку:

1. появился свежий handshake;
2. пингуется VPN-адрес сервера;
3. DNS отвечает;
4. открывается короткая HTTPS-страница;
5. внешний IP соответствует ожидаемому выходу;
6. крупная загрузка не зависает из-за MTU.

Если handshake есть, но интернета нет, причина обычно в forward, NAT, DNS или
обратном маршруте, а не в ключах.

## 11. Добавить нового клиента без простоя

Создайте датированную резервную копию постоянного конфига:

```bash
sudo cp -a /etc/amnezia/amneziawg/awg0.conf \
  /etc/amnezia/amneziawg/awg0.conf.before-client-$(date -u +%Y%m%dT%H%M%SZ)
```

Добавьте `[Peer]` в файл через `sudoedit`, затем примените peer без рестарта:

```bash
sudo awg set awg0 peer '<CLIENT_PUBLIC_KEY>' allowed-ips 10.66.0.3/32
sudo awg show awg0 allowed-ips
```

Так существующие подключения не обрываются. Перед следующей перезагрузкой
сравните runtime и постоянную конфигурацию.

## 12. Автозапуск и контроль после reboot

```bash
sudo systemctl is-enabled awg-quick@awg0
sudo systemctl is-active awg-quick@awg0
modinfo amneziawg
sudo awg show awg0
```

Отдельно проверьте восстановление nftables и policy routing. `awg-quick` не
восстановит сторонние таблицы маршрутизации автоматически, если они не описаны
в unit/service loader.

## 13. Безопасный откат

Если новая настройка нарушила сеть:

1. не удаляйте конфиги и резервные копии;
2. остановите только новый интерфейс после разрешения владельца;
3. верните предыдущий конфиг копированием поверх рабочего только после сверки;
4. загрузите прежние nftables/policy rules;
5. повторите проверки физической сети и SSH;
6. не перезагружайте сервер, пока не понятен способ восстановления удалённого
   доступа.
