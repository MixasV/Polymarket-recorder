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

## Autostart & Reliability

### 🐧 Linux (systemd) - Recommended
To ensure the recorder starts on boot and restarts automatically if it crashes:
1. Edit `recorder.service` and update `User`, `WorkingDirectory`, and `ExecStart` paths.
2. Copy the service file:
   ```bash
   sudo cp recorder.service /etc/systemd/system/recorder.service
   ```
3. Enable and start:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable recorder
   sudo systemctl start recorder
   ```
4. Check logs: `journalctl -u recorder -f`

### 🪟 Windows (Task Scheduler)
1. Open **Task Scheduler** and create a new task.
2. Set **Trigger** to "At log on" or "At startup".
3. Set **Action** to "Start a program":
   - **Program**: `path\to\venv\Scripts\python.exe`
   - **Arguments**: `data_recorder.py`
   - **Start in**: `path\to\Polymarket-recorder`
4. In **Settings**, check "If the task fails, restart every: 1 minute".

### ⚙️ Non-interactive Mode
The script detects if it's running in a service. You can force proxy settings via environment variables:
- `USE_PROXY=true` or `USE_PROXY=false`

---

# Регистратор данных Polymarket BTC 15m (RU)

Скрипт для непрерывной записи цен Bitcoin (Binance) и данных рынков Polymarket в режиме реального времени. Предназначен для сбора данных для бэктестов и анализа стратегий.

## Автозапуск и отказоустойчивость

### 🐧 Linux (systemd) — Рекомендуется
Для автоматического запуска при загрузке и перезапуске при сбоях:
1. Отредактируйте `recorder.service`, указав правильные пути в `User`, `WorkingDirectory` и `ExecStart`.
2. Скопируйте файл сервиса:
   ```bash
   sudo cp recorder.service /etc/systemd/system/recorder.service
   ```
3. Активируйте и запустите:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable recorder
   sudo systemctl start recorder
   ```
4. Просмотр логов: `journalctl -u recorder -f`

### 🪟 Windows (Планировщик задач)
1. Откройте **Планировщик задач** и создайте новую задачу.
2. **Триггер**: "При входе в систему" или "При запуске".
3. **Действие**: "Запуск программы":
   - **Программа**: `путь\к\venv\Scripts\python.exe`
   - **Аргументы**: `data_recorder.py`
   - **Рабочая папка**: `путь\к\Polymarket-recorder`
4. В **Параметрах** включите "При сбое перезапускать через: 1 мин".

### ⚙️ Неинтерактивный режим
Скрипт автоматически определяет запуск в фоне. Вы можете принудительно задать использование прокси через переменную окружения:
- `USE_PROXY=true` или `USE_PROXY=false`
