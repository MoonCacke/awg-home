# Xray: VLESS REALITY

VLESS сам по себе не шифрует внешний транспорт. Для публичного соединения в
этом руководстве используется REALITY и поток `xtls-rprx-vision`.

## 1. Установка

Устанавливайте Xray-core только из официальных релизов или официального
install-script проекта XTLS. Зафиксируйте установленную версию:

```bash
xray version
```

Документация Xray может описывать более новую версию, чем установленная.
Перед применением нового поля сверяйте его поддержку командой проверки
конфигурации.

## 2. Секреты

```bash
xray uuid
xray x25519
openssl rand -hex 8
```

Результаты используются как:

- UUID VLESS — отдельный для каждого клиента;
- private key REALITY — только на сервере;
- password/public key REALITY — на клиенте;
- short ID — чётное число hex-символов, максимум 16.

Не публикуйте UUID, REALITY private key, клиентские URI и JSON-профили.

## 3. Target/SNI

REALITY `target` должен быть стабильным TLS 1.3-сайтом, доступным серверу.
`serverNames` обычно содержит имя из сертификата target. Проверка:

```bash
xray tls ping example.com
```

Не копируйте `example.com` из шаблона буквально. Выберите подходящий target и
учтите предупреждение Xray: неаутентифицированные соединения пересылаются к
target, поэтому неудачный выбор может превратить сервер в нежелательный
ретранслятор.

## 4. Сервер

Используйте [`../examples/xray-server-reality.json.example`](../examples/xray-server-reality.json.example).
Перед перезапуском:

```bash
sudo xray run -test -config /usr/local/etc/xray/config.json
sudo systemctl restart xray
sudo systemctl status xray --no-pager
sudo journalctl -u xray -n 50 --no-pager
```

Откройте в firewall только фактический TCP-порт Xray. Если используется `443`,
заранее убедитесь, что его не занимает Apache, Nginx или другой сервис.

## 5. Клиент

Для Xray-core используйте
[`../examples/xray-client-reality.json.example`](../examples/xray-client-reality.json.example).
Для Happ и совместимых клиентов можно импортировать URI:

```text
vless://<UUID>@<SERVER_IP_OR_NAME>:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=<SNI>&fp=chrome&pbk=<REALITY_PUBLIC_KEY>&sid=<SHORT_ID>&type=tcp&headerType=none#HOME-Reality
```

URI равнозначен паролю доступа: QR-код и скриншот нельзя публиковать.

В новых версиях Xray поле REALITY public key в JSON называется `password`.
Старые клиенты могут ожидать имя `publicKey`; ориентируйтесь на версию клиента.
Аналогично транспорт `tcp` в новых схемах документации может называться `raw`:
не меняйте это поле без проверки версии обеих сторон.

## 6. Проверка

На сервере:

```bash
sudo ss -ltnp | grep ':443'
sudo journalctl -u xray -f
```

На клиенте сначала проверьте короткую страницу и DNS, затем крупную загрузку.
Статус «подключено» в приложении означает только созданный локальный VPN/TUN;
он не подтверждает успешную авторизацию VLESS на сервере.
