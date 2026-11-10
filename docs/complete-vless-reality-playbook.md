# Полное развёртывание Xray/VLESS REALITY

Руководство описывает Xray-core с VLESS, REALITY и
`xtls-rprx-vision` на публичном VPS. Все значения в `<...>` должны быть
заменены. Не публикуйте заполненный JSON, URI или QR-код.

## 0. Карта параметров

| Параметр | Значение |
|---|---|
| Сервер | `<VPS_NAME>` |
| Публичный адрес | `<SERVER_IP_OR_NAME>` |
| TCP-порт | `443` или `<VLESS_PORT>` |
| UUID клиента | `<CLIENT_UUID>` |
| REALITY target | `<TARGET_HOST>:443` |
| SNI | `<TARGET_HOST>` |
| REALITY private key | только сервер |
| REALITY public key/password | клиент |
| Short ID | `<16_HEX_CHARS>` |

## 1. Предварительный аудит

```bash
date -u
hostnamectl
uname -a
ip -br address
ip -4 route
sudo ss -ltnp
sudo nft list ruleset
sudo systemctl --failed
command -v xray || true
xray version 2>/dev/null || true
```

Если порт `443` уже занят Apache/Nginx/Caddy, выберите другой внешний порт или
спроектируйте явный reverse proxy/fallback. Не останавливайте действующий сайт
ради Xray без отдельного решения.

## 2. Установка Xray

Используйте официальный проект:

- <https://github.com/XTLS/Xray-core>
- <https://github.com/XTLS/Xray-install>

Не передавайте скачанный скрипт прямо в `bash` через pipe. Скачайте его,
прочитайте и только после разрешения владельца запустите:

```bash
curl -fL \
  https://github.com/XTLS/Xray-install/raw/main/install-release.sh \
  -o /tmp/xray-install.sh
less /tmp/xray-install.sh
sudo bash /tmp/xray-install.sh install
```

Не удаляйте `/tmp/xray-install.sh` без разрешения владельца. После установки:

```bash
xray version
systemctl cat xray
sudo systemctl status xray --no-pager
```

## 3. Создать идентификаторы

```bash
xray uuid
xray x25519
openssl rand -hex 8
```

Запишите секреты в защищённое локальное хранилище. Для каждого пользователя
создавайте отдельный UUID. Short ID должен иметь чётное количество hex-символов
и не более 16 символов.

В современных версиях Xray публичная часть REALITY может называться
`password`; старые клиенты называют её `publicKey` или передают параметром
`pbk` в URI.

## 4. Выбрать REALITY target

Target должен:

- быть доступен VPS напрямую;
- поддерживать TLS 1.3;
- стабильно отвечать на `443/tcp`;
- иметь сертификат, включающий выбранный SNI;
- по возможности находиться в том же ASN/регионе, чтобы маршрут выглядел
  естественно;
- не создавать опасный открытый fallback к крупному CDN.

Проверка:

```bash
xray tls ping <TARGET_HOST>
```

Не используйте фиктивный target из шаблона.

## 5. Подготовить серверный JSON

Возьмите
[`../examples/xray-server-reality.json.example`](../examples/xray-server-reality.json.example)
и заполните копию вне Git. Стандартный путь официальной установки:

```text
/usr/local/etc/xray/config.json
```

Перед изменением существующего файла сделайте датированную копию:

```bash
sudo cp -a /usr/local/etc/xray/config.json \
  /usr/local/etc/xray/config.json.before-reality-$(date -u +%Y%m%dT%H%M%SZ)
```

Редактируйте через:

```bash
sudoedit /usr/local/etc/xray/config.json
```

Права должны позволять чтение служебному пользователю Xray, но не всем
пользователям системы.

## 6. Проверить до перезапуска

```bash
sudo xray run -test -config /usr/local/etc/xray/config.json
```

Дальше проверьте firewall. Разрешить нужно только выбранный TCP-порт. Если
используется UFW:

```bash
sudo ufw status verbose
```

Не включайте новый firewall вслепую на удалённом сервере: сначала гарантируйте
правило SSH.

## 7. Применить конфигурацию

Только после успешной проверки и отдельного разрешения:

```bash
sudo systemctl restart xray
sudo systemctl status xray --no-pager
sudo journalctl -u xray -n 80 --no-pager
sudo ss -ltnp | grep ':<VLESS_PORT>'
```

Если служба не поднялась, не перезагружайте VPS. Верните предыдущий JSON и
повторите `xray run -test`.

## 8. Создать клиент

Вариант для Xray-core:

[`../examples/xray-client-reality.json.example`](../examples/xray-client-reality.json.example)

Вариант URI для Happ/v2rayN-совместимого клиента:

```text
vless://<UUID>@<SERVER_IP_OR_NAME>:<PORT>?encryption=none&flow=xtls-rprx-vision&security=reality&sni=<SNI>&fp=chrome&pbk=<REALITY_PUBLIC_KEY>&sid=<SHORT_ID>&type=tcp&headerType=none#HOME-Reality
```

После импорта проверьте, что приложение не изменило:

- адрес и порт;
- UUID;
- `flow=xtls-rprx-vision`;
- SNI;
- fingerprint;
- public key/password;
- short ID;
- транспорт TCP/RAW.

## 9. Проверить сессию

Сначала включите временно более подробный лог только если это безопасно. Затем:

```bash
sudo journalctl -u xray -f
```

На клиенте:

1. открыть DNS/trace-страницу;
2. проверить внешний IP;
3. отправить короткое сообщение;
4. проверить обычную HTTPS-страницу;
5. проверить видео или крупную загрузку;
6. повторить тест отдельно через Wi-Fi и мобильную сеть.

Если приложение показывает VPN-значок, но на сервере нет новой сессии, создан
только локальный TUN. Проверяйте адрес, порт, SNI, UUID, key и short ID.

## 10. Добавить нового пользователя

Не передавайте один UUID нескольким людям. Для нового устройства:

1. `xray uuid`;
2. добавить отдельную запись в `settings.clients`;
3. сохранить резервную копию JSON;
4. выполнить `xray run -test`;
5. перезапустить Xray только с разрешения;
6. проверить журнал и порт;
7. сформировать отдельный URI/QR;
8. передать секрет через доверенный канал.

REALITY keypair можно оставить общим для одного inbound, а UUID должен быть
отдельным. При компрометации профиля отзывайте его UUID.

## 11. Split routing

На клиенте можно направлять через VLESS только выбранные домены/IP. На Xray
это делается блоком `routing`, тегами outbound и встроенным DNS. Важные правила:

- DNS должен проходить по той же логике, что и целевой трафик;
- общие CDN-IP могут принадлежать нескольким сервисам;
- QUIC/UDP 443 может идти иным путём, чем TCP;
- для диагностики сначала используйте полный туннель, затем добавляйте split.

## 12. Автозапуск и обновления

```bash
sudo systemctl is-enabled xray
sudo systemctl is-active xray
xray version
sudo xray run -test -config /usr/local/etc/xray/config.json
```

Перед обновлением сохраните бинарную версию и конфиг. После обновления сначала
проверьте JSON новой версией и только потом перезапускайте службу.

## 13. Безопасный откат

1. не удалять рабочий и резервный JSON;
2. проверить старый JSON командой `xray run -test`;
3. восстановить его только после сверки путей и прав;
4. перезапустить только Xray;
5. проверить SSH, сайт, AWG и OpenClaw отдельно;
6. зафиксировать причину отката и версии клиента/сервера.
