# Polymarket BTC 15m Data Recorder

Continuous real-time data recorder for Bitcoin prices (Binance) and Polymarket prediction market data. Designed for high-frequency data collection to support backtesting and strategy analysis.

## Features

- **Multi-Source Recording**: Captures Binance spot prices, Polymarket Orderbook (CLOB), Oracle prices (RTDS), and Target prices.
- **Asynchronous & Non-Blocking**: Uses `asyncio` for network operations and a dedicated background `DBWriter` thread for SQLite operations to ensure zero data loss during high volatility.
- **Daily Rotation**: Automatically creates a new SQLite database every day (`db/recorder_YYYY-MM-DD.db`) for easy data management.
- **Health Monitoring**: Built-in connection watchdog and heartbeat system to monitor data feed stability.
- **Real-time Console UI**: Live status line showing current prices, latency (lag), and connection status.
- **Proxy Support**: Built-in support for proxies to bypass regional restrictions on Polymarket APIs.

---

## Installation Guide

### Prerequisites
- **Python 3.10 or higher**
- **Git**

### 🪟 Windows Installation
1. **Clone the repository**:
   ```bash
   git clone https://github.com/MixasV/Polymarket-recorder.git
   cd Polymarket-recorder
   ```
2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   ```
3. **Activate the environment**:
   ```bash
   .\venv\Scripts\activate
   ```
4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

### 🐧 Linux Installation (Ubuntu/Debian/CentOS)
1. **Clone the repository**:
   ```bash
   git clone https://github.com/MixasV/Polymarket-recorder.git
   cd Polymarket-recorder
   ```
2. **Install Python venv package** (if missing):
   ```bash
   sudo apt update
   sudo apt install python3-venv -y
   ```
3. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   ```
4. **Activate the environment**:
   ```bash
   source venv/bin/activate
   ```
5. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## Usage

### Running the Recorder
1. Ensure your environment is activated.
2. Start the script:
   ```bash
   python data_recorder.py
   ```
3. On startup, the script will ask: `Use proxy for Polymarket? (y/n)`. 
   - Press **Enter** or **y** to enable proxy (configured in `data/clients.py`).
   - Press **n** for direct connection.

### Running in background (Linux)
To keep the recorder running after closing the SSH session, use `screen` or `tmux`:
```bash
screen -S recorder
source venv/bin/activate
python data_recorder.py
# Press Ctrl+A then D to detach
```

### Console Indicators
- `BNC`: Latest Binance BTC price.
- `ORC`: Latest Polymarket Oracle price.
- `LAG`: Latency between Binance and Oracle in milliseconds.
- `U/D`: Best Bid/Ask for UP and DOWN tokens.
- `Mkt`: Currently active Polymarket 15m BTC market.

---

# Регистратор данных Polymarket BTC 15m (RU)

Скрипт для непрерывной записи цен Bitcoin (Binance) и данных рынков Polymarket в режиме реального времени. Предназначен для сбора данных для бэктестов и анализа стратегий.

## Инструкция по установке

### Требования
- **Python 3.10 или выше**
- **Git**

### 🪟 Установка на Windows
1. **Клонируйте репозиторий**:
   ```bash
   git clone https://github.com/MixasV/Polymarket-recorder.git
   cd Polymarket-recorder
   ```
2. **Создайте виртуальное окружение**:
   ```bash
   python -m venv venv
   ```
3. **Активируйте окружение**:
   ```bash
   .\venv\Scripts\activate
   ```
4. **Установите зависимости**:
   ```bash
   pip install -r requirements.txt
   ```

### 🐧 Установка на Linux (Ubuntu/Debian)
1. **Клонируйте репозиторий**:
   ```bash
   git clone https://github.com/MixasV/Polymarket-recorder.git
   cd Polymarket-recorder
   ```
2. **Установите пакет venv** (если не установлен):
   ```bash
   sudo apt update
   sudo apt install python3-venv -y
   ```
3. **Создайте виртуальное окружение**:
   ```bash
   python3 -m venv venv
   ```
4. **Активируйте окружение**:
   ```bash
   source venv/bin/activate
   ```
5. **Установите зависимости**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

## Использование

### Запуск
```bash
python data_recorder.py
```
При запуске скрипт спросит: `Use proxy for Polymarket? (y/n)`.
- Нажмите **y** или **Enter** для использования прокси.
- Нажмите **n** для прямого подключения.

### Запуск в фоне (Linux)
Используйте `screen` для стабильной работы:
```bash
screen -S recorder
source venv/bin/activate
python data_recorder.py
# Нажмите Ctrl+A, затем D для выхода из сессии
```

## Структура данных
Данные сохраняются в `db/recorder_YYYY-MM-DD.db`:
- `market_snapshots`: Посекундные котировки (~3 записи в секунду).
- `system_events`: Журнал переключения рынков и ошибок связи.
