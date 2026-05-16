# Flood Prediction and Early Warning System 洪水预测与预警系统

Based on LSTM-Attention, predicts flood risk using 72-hour hydrological data to forecast water levels for the next 24 hours.

基于LSTM-Attention的洪水预测与预警系统，利用过去72小时水文数据预测未来24小时水位变化。

## Team 组别

**Group 3 / 第3组** | Course: Smart Water Resources Application / 智慧水利应用

| Member 成员 | Role 角色 | Responsibilities 职责 |
|------------|-----------|---------------------|
| 庞雯乐 | TBD | TBD |
| 李杨芷慧 | TBD | TBD |
| 陈心怡 | TBD | TBD |

## Architecture 系统架构

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐    ┌──────────────┐
│  Data       │───▶│  Data       │───▶│  LSTM-       │───▶│  Warning     │
│  Collection │    │  Processing │    │  Attention   │    │  Service     │
│  (Sensors)  │    │  (Validate) │    │  Model       │    │  (Alert)     │
└─────────────┘    └─────────────┘    └──────────────┘    └──────────────┘
       │                                                         │
       └─────────────────────── RESTful API ─────────────────────┘
                                      │
                            FastAPI Web Server
```

## Project Structure 项目结构

```
flood-prediction-system/
├── src/
│   ├── config/settings.py        # System configuration
│   ├── data_collection/          # Data collection module
│   │   ├── sensor_simulator.py   #   Sensor simulation (water level, rainfall, quality)
│   │   └── data_collector.py     #   Data collection service
│   ├── data_processing/          # Data processing module
│   │   ├── data_validator.py     #   Data validation & cleaning
│   │   └── data_preprocessor.py  #   Data preprocessing (normalization, sequencing)
│   ├── prediction_model/         # Prediction model module
│   │   ├── lstm_attention.py     #   LSTM-Attention model definition
│   │   ├── trainer.py            #   Model trainer
│   │   ├── predictor.py          #   Prediction service
│   │   └── warning_service.py    #   Warning service
│   ├── db/                       # Database module
│   │   ├── models.py             #   ORM models (8 tables)
│   │   └── init_db.py            #   DB initialization
│   └── web/                      # Web API module
│       ├── app.py                #   FastAPI application
│       └── routes.py             #   API route definitions
├── tests/                        # Unit tests
│   ├── test_data_collection.py
│   ├── test_data_processing.py
│   └── test_prediction_model.py
├── scripts/
│   └── run_pipeline.py           # End-to-end pipeline demo
├── docs/
│   └── assignment_report.md      # Progress report
├── ai_plan/
│   └── ai_instructions.md        # AI programming records
├── requirements.txt
└── README.md
```

## Modules 模块说明

### 1. Data Collection 数据采集

| Class | Function | Description |
|-------|----------|-------------|
| `WaterLevelSensor` | `read_data()` | Simulates water level readings with diurnal cycle + noise |
| `RainfallSensor` | `read_data()` | Simulates rainfall events with Markov process |
| `WaterQualitySensor` | `read_data()` | Simulates pH, turbidity, dissolved oxygen |
| `SensorDataCollector` | `collect_all_data()` | Manages 5 monitoring stations |
| `DataCollectionService` | `collect_realtime_data()` | High-level collection interface |

### 2. Data Processing 数据处理

| Class | Function | Description |
|-------|----------|-------------|
| `DataValidator` | `validate_water_data()` | Range/logical/timestamp validation |
| `DataValidator` | `batch_validate()` | Batch validation |
| `DataPreprocessor` | `normalize_data()` | Min-Max normalization |
| `DataPreprocessor` | `standardize_data()` | Z-score standardization |
| `DataPreprocessor` | `create_sequences()` | Time series windowing |
| `DataPreprocessor` | `prepare_training_data()` | Feature/label generation |

### 3. LSTM-Attention Model 预测模型

| Class | Function | Description |
|-------|----------|-------------|
| `AttentionLayer` | `forward()` | Additive attention mechanism |
| `LSTMAttentionModel` | `forward()` | BiLSTM + Attention + FC |
| `ModelTrainer` | `fit()` | Training loop with early stopping |
| `FloodPredictor` | `predict_flood_risk()` | Risk assessment & prediction |

**Algorithm**: Bidirectional LSTM extracts temporal features → Attention layer focuses on critical time steps → Fully connected layer outputs 24-hour water level predictions.

**Parameters**: input_size=7, hidden_size=128, num_layers=2, output_size=24, seq_length=72

### 4. Warning Service 预警服务

| Class | Function | Description |
|-------|----------|-------------|
| `WarningService` | `create_warning()` | Create warning (4 levels) |
| `WarningService` | `send_warning()` | Multi-channel alert sending |
| `WarningService` | `generate_flood_warning()` | Auto-generate from prediction |

Warning levels: Blue (1), Yellow (2), Orange (3), Red (4)

### 5. Database 数据库

8 tables with SQLAlchemy ORM:

- `monitor_station` - Station info
- `water_monitoring_data` - Hydrological time-series
- `water_quality_data` - Water quality data
- `flood_prediction_record` - Prediction records
- `warning_info` - Warning information
- `model_version` - Model version management

### 6. Web API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/water-data/realtime` | GET | Real-time hydrological data |
| `/api/v1/sensor-data` | POST | Submit sensor data |
| `/api/v1/prediction/flood-risk` | GET | Flood risk prediction |
| `/api/v1/warnings` | POST | Create warning |
| `/api/v1/warnings/active` | GET | Active warnings list |
| `/api/v1/stations` | GET | Station list |

## Quick Start 快速开始

### Requirements

```bash
pip install -r requirements.txt
```

### Run Pipeline Demo

```bash
cd flood-prediction-system
python scripts/run_pipeline.py
```

### Start API Server

```bash
uvicorn src.web.app:app --reload
# Visit http://localhost:8000/docs for Swagger UI
```

### Run Tests

```bash
pytest tests/ -v
```

## Development Schedule 开发进度

| Phase | Duration | Status |
|-------|----------|--------|
| Week 1: Architecture & Core Modules | 5.14 - 5.20 | ✅ Completed |

## AI-Assisted Programming

This project follows AI-assisted programming standard workflow. See [ai_plan/](ai_plan/) for detailed AI instruction records.

## License

Course project for educational purposes.
