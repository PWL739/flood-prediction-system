"""模型训练器 —— 负责LSTM-Attention模型的训练和评估"""

import torch
import torch.nn as nn
import numpy as np
from torch.utils.data import DataLoader, TensorDataset
from typing import Optional, Callable
from src.config.settings import MODEL_CONFIG
from src.prediction_model.lstm_attention import LSTMAttentionModel


class ModelTrainer:
    """模型训练器"""

    def __init__(self, model: Optional[LSTMAttentionModel] = None):
        self.model = model or LSTMAttentionModel()
        self.criterion = nn.MSELoss()
        self.optimizer = torch.optim.Adam(
            self.model.parameters(), lr=MODEL_CONFIG["learning_rate"]
        )
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="min", factor=0.5, patience=10, verbose=True
        )
        self.train_losses = []
        self.val_losses = []

    def train_epoch(self, dataloader: DataLoader) -> float:
        """训练一个epoch"""
        self.model.train()
        total_loss = 0

        for batch_x, batch_y in dataloader:
            self.optimizer.zero_grad()
            output = self.model(batch_x)
            loss = self.criterion(output, batch_y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()
            total_loss += loss.item()

        return total_loss / len(dataloader)

    @torch.no_grad()
    def evaluate(self, dataloader: DataLoader) -> float:
        """评估模型"""
        self.model.eval()
        total_loss = 0

        for batch_x, batch_y in dataloader:
            output = self.model(batch_x)
            loss = self.criterion(output, batch_y)
            total_loss += loss.item()

        return total_loss / len(dataloader)

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        batch_size: int = None,
        num_epochs: int = None,
        callback: Optional[Callable] = None,
    ):
        """完整训练流程"""
        if batch_size is None:
            batch_size = MODEL_CONFIG["batch_size"]
        if num_epochs is None:
            num_epochs = MODEL_CONFIG["num_epochs"]

        # 准备数据加载器
        train_dataset = TensorDataset(
            torch.FloatTensor(X_train), torch.FloatTensor(y_train)
        )
        train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

        val_loader = None
        if X_val is not None and y_val is not None:
            val_dataset = TensorDataset(
                torch.FloatTensor(X_val), torch.FloatTensor(y_val)
            )
            val_loader = DataLoader(val_dataset, batch_size=batch_size)

        # 训练循环
        for epoch in range(num_epochs):
            train_loss = self.train_epoch(train_loader)
            self.train_losses.append(train_loss)

            if val_loader:
                val_loss = self.evaluate(val_loader)
                self.val_losses.append(val_loss)
                self.scheduler.step(val_loss)
                print(
                    f"Epoch {epoch+1}/{num_epochs} | "
                    f"Train Loss: {train_loss:.6f} | Val Loss: {val_loss:.6f}"
                )
            else:
                print(f"Epoch {epoch+1}/{num_epochs} | Train Loss: {train_loss:.6f}")

            if callback:
                callback(epoch, train_loss, val_loss if val_loader else None)

    def save_model(self, filepath: str):
        """保存模型权重"""
        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "train_losses": self.train_losses,
                "val_losses": self.val_losses,
            },
            filepath,
        )
        print(f"模型已保存至: {filepath}")

    def load_model(self, filepath: str):
        """加载模型权重"""
        checkpoint = torch.load(filepath, map_location="cpu")
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.train_losses = checkpoint["train_losses"]
        self.val_losses = checkpoint.get("val_losses", [])
        print(f"模型已从 {filepath} 加载")
