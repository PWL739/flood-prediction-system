"""LSTM-Attention 模型实现 —— 对应详细设计文档算法设计部分

使用过去72小时的水文数据预测未来24小时的水位变化
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from src.config.settings import MODEL_CONFIG


class AttentionLayer(nn.Module):
    """注意力机制层 —— 自动聚焦关键时间步的影响"""

    def __init__(self, lstm_output_size: int, attention_size: int = None):
        super().__init__()
        if attention_size is None:
            attention_size = MODEL_CONFIG["attention_size"]
        self.attention_size = attention_size

        self.attention_weights = nn.Sequential(
            nn.Linear(lstm_output_size + lstm_output_size, attention_size),
            nn.Tanh(),
            nn.Linear(attention_size, 1),
        )

    def forward(self, lstm_output: torch.Tensor, hidden_state: torch.Tensor):
        """
        Args:
            lstm_output: LSTM所有时间步输出 [batch, seq_len, lstm_output_size]
            hidden_state: LSTM最后隐藏状态 [batch, lstm_output_size]
        Returns:
            context: 加权上下文向量 [batch, lstm_output_size]
            attention_weights: 注意力权重 [batch, seq_len]
        """
        # 扩展隐藏状态以匹配时间步
        hidden = hidden_state.unsqueeze(1).repeat(1, lstm_output.size(1), 1)

        # 拼接LSTM输出和隐藏状态
        combined = torch.cat((lstm_output, hidden), dim=2)

        # 计算注意力分数
        energy = self.attention_weights(combined).squeeze(2)

        # Softmax归一化
        attention_weights = F.softmax(energy, dim=1)

        # 加权求和
        context = torch.bmm(attention_weights.unsqueeze(1), lstm_output).squeeze(1)

        return context, attention_weights


class LSTMAttentionModel(nn.Module):
    """LSTM-Attention 洪水预测模型"""

    def __init__(
        self,
        input_size: int = None,
        hidden_size: int = None,
        num_layers: int = None,
        output_size: int = None,
        dropout: float = None,
    ):
        super().__init__()

        self.input_size = input_size or MODEL_CONFIG["input_size"]
        self.hidden_size = hidden_size or MODEL_CONFIG["hidden_size"]
        self.num_layers = num_layers or MODEL_CONFIG["num_layers"]
        self.output_size = output_size or MODEL_CONFIG["output_size"]
        self.dropout = dropout or MODEL_CONFIG["dropout"]

        # LSTM层
        self.lstm = nn.LSTM(
            input_size=self.input_size,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=self.dropout if self.num_layers > 1 else 0,
        )

        # 注意力层（bidirectional LSTM输出维度为 hidden_size * 2）
        self.attention = AttentionLayer(self.hidden_size * 2)

        # 输出层（context = 2H, hidden_combined = 2H, 拼接后 = 4H）
        self.fc = nn.Sequential(
            nn.Linear(self.hidden_size * 4, self.hidden_size),
            nn.ReLU(),
            nn.Dropout(self.dropout),
            nn.Linear(self.hidden_size, self.output_size),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: 输入序列 [batch, seq_len, input_size]
        Returns:
            output: 预测值 [batch, output_size]
        """
        # LSTM前向传播
        lstm_output, (hidden, cell) = self.lstm(x)

        # 使用最后一层的隐藏状态（双向拼接）
        hidden_combined = torch.cat((hidden[-2, :, :], hidden[-1, :, :]), dim=1)

        # 注意力机制
        context, attention_weights = self.attention(lstm_output, hidden_combined)

        # 拼接上下文向量和隐藏状态
        combined = torch.cat((context, hidden_combined), dim=1)

        # 输出层
        output = self.fc(combined)

        return output

    def predict_with_attention(self, x: torch.Tensor) -> dict:
        """预测并返回注意力权重（用于可视化）"""
        lstm_output, (hidden, cell) = self.lstm(x)
        hidden_combined = torch.cat((hidden[-2, :, :], hidden[-1, :, :]), dim=1)
        context, attention_weights = self.attention(lstm_output, hidden_combined)
        combined = torch.cat((context, hidden_combined), dim=1)
        output = self.fc(combined)

        return {
            "prediction": output,
            "attention_weights": attention_weights,
        }


def build_model() -> LSTMAttentionModel:
    """构建LSTM-Attention模型实例"""
    return LSTMAttentionModel()
