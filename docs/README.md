# Документация AWG Home

Этот каталог описывает безопасную сборку собственной VPN-схемы на базе
AmneziaWG и Xray/VLESS REALITY. Все адреса, ключи, UUID и домены в примерах —
фиктивные. Рабочие профили сюда добавлять нельзя.

## С чего начать

1. [Архитектура](architecture.md) — варианты одного и двух узлов.
2. [AmneziaWG](amneziawg.md) — сервер, клиенты, роутер и проверка.
   Полная процедура: [complete-awg-playbook.md](complete-awg-playbook.md).
3. [VLESS REALITY](vless-reality.md) — Xray, сервер и клиент.
   Полная процедура: [complete-vless-reality-playbook.md](complete-vless-reality-playbook.md).
4. [Маршрутизация](routing.md) — полный, раздельный и каскадный режимы.
5. [Эксплуатация](operations.md) — диагностика, обновления и восстановление.
6. [Безопасность](security.md) — секреты, SSH, firewall и публикация в Git.

Готовые обезличенные заготовки находятся в [`../examples`](../examples).
Промты для соседних чатов находятся в [`../prompts`](../prompts).

## Важная граница

AWG и VLESS решают разные задачи:

- **AmneziaWG** — быстрый полноценный IP-туннель, обычно по UDP.
- **VLESS REALITY** — прокси-транспорт поверх TCP/TLS-подобного соединения,
  который полезен в сетях, где UDP или характерный VPN-трафик ограничивается.

Ни один протокол сам по себе не делает пользователя анонимным. Сервер выхода,
сайт и оператор всё равно видят метаданные, соответствующие своей позиции в
маршруте.

## Первичные источники

- [AmneziaWG](https://docs.amnezia.org/documentation/amnezia-wg/)
- [Модуль AmneziaWG для Linux](https://docs.amnezia.org/documentation/instructions/install-amneziawg-kernel-module-linux/)
- [Xray: VLESS](https://xtls.github.io/en/config/outbounds/vless.html)
- [Xray: REALITY](https://xtls.github.io/en/config/transports/reality.html)
