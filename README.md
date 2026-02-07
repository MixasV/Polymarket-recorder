# Polymarket BTC 15m Data Recorder

Continuous real-time data recorder for Bitcoin prices (Binance) and Polymarket prediction market data. Designed for high-frequency data collection to support backtesting and strategy analysis.

## Features

- **Multi-Source Recording**: Captures Binance spot prices, Polymarket Orderbook (CLOB), Oracle prices (RTDS), and Target prices.
- **Asynchronous & Non-Blocking**: Uses `asyncio` for network operations and a dedicated background `DBWriter` thread for SQLite operations to ensure zero data loss during high volatility.
- **Daily Rotation**: Automatically creates a new SQLite database every day (`db/recorder_YYYY-MM-DD.db`) for easy data management.
- **Health Monitoring**: Built-in connection watchdog and heartbeat system to monitor data feed stability.
- **Real-time Console UI**: Live status line showing current prices, latency (lag), and connection status.
- **Proxy Support**: Built-in support for proxies to bypass regional restrictions on Polymarket APIs.

## Installation

1. **Requirements**: Python 3.10 or higher.
2. **Setup**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Configuration**: Ensure your `.env` file (if used) is configured or be ready to toggle proxy settings on startup.

## Usage

Start the recorder:
```bash
python data_recorder.py
```

### Console Indicators:
- `BNC`: Latest Binance BTC price.
- `ORC`: Latest Polymarket Oracle price.
- `LAG`: Latency between Binance and Oracle in milliseconds.
- `U/D`: Best Bid/Ask for UP and DOWN tokens.
- `Mkt`: Currently active Polymarket 15m BTC market.

## Data Structure

Data is stored in `db/recorder_YYYY-MM-DD.db` with the following tables:
- `market_snapshots`: Tick-by-tick price data (~3Hz).
- `system_events`: Logs of market switches, connection issues, and resolutions.

---

# Регистратор данных Polymarket BTC 15m

Скрипт для непрерывной записи цен Bitcoin (Binance) и данных рынков Polymarket в режиме реального времени.

## Основные возможности

- **Запись из нескольких источников**: Binance, Polymarket Orderbook, Oracle (RTDS) и целевые цены (Target Prices).
- **Фоновая запись в БД**: Использование отдельного потока `DBWriter` для неблокирующей записи в SQLite.
- **Ротация базы данных**: Ежедневное создание новой БД (`db/recorder_YYYY-MM-DD.db`).
- **Мониторинг здоровья**: Встроенный ворчдог для контроля стабильности соединений.
- **Прокси**: Поддержка прокси для работы с API Polymarket.

## Запуск

```bash
python data_recorder.py
```
При запуске скрипт предложит включить или выключить прокси.
