# Data Recorder

Continuous recording of BTC prices (Binance) and Polymarket data (Orderbook, Oracle, Target Prices).

## Installation

1. Install Python 3.10+
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

When the script starts, it will ask if you want to use a proxy. 
You can also update proxy settings in `data/clients.py` if needed:
- `PROXY_HOST`
- `PROXY_PORT`
- `PROXY_USER`
- `PROXY_PASS`

## Usage

Run the recorder:
```bash
python data_recorder.py
```

The data will be saved in the `db/` folder as SQLite databases (e.g., `recorder_YYYY-MM-DD.db`).
