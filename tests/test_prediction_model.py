"""预测模型单元测试"""

import pytest
import torch
from src.prediction_model.lstm_attention import LSTMAttentionModel, build_model
from src.prediction_model.predictor import FloodPredictor


class TestLSTMAttentionModel:
    def test_model_creation(self):
        model = build_model()
        assert isinstance(model, LSTMAttentionModel)
        assert model.input_size == 7
        assert model.output_size == 24

    def test_forward_pass(self):
        model = build_model()
        batch_size, seq_len = 4, 72
        dummy_input = torch.randn(batch_size, seq_len, model.input_size)
        output = model(dummy_input)
        assert output.shape == (batch_size, model.output_size)

    def test_forward_pass_single_batch(self):
        model = build_model()
        dummy_input = torch.randn(1, 72, model.input_size)
        output = model(dummy_input)
        assert output.shape == (1, model.output_size)

    def test_predict_with_attention(self):
        model = build_model()
        dummy_input = torch.randn(1, 72, model.input_size)
        result = model.predict_with_attention(dummy_input)
        assert "prediction" in result
        assert "attention_weights" in result
        assert result["attention_weights"].shape[1] == 72
