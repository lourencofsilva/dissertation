"""
This module contains the Evaluator class which is used to evaluate the ML models.
"""
from sklearn.metrics import mean_absolute_error, mean_squared_error, mean_absolute_percentage_error

class Evaluator:
    def __init__(self, y_true, y_pred):
        self.y_true = y_true
        self.y_pred = y_pred

    def compute_metrics(self):
        mae = mean_absolute_error(self.y_true, self.y_pred)
        mse = mean_squared_error(self.y_true, self.y_pred)
        mape = mean_absolute_percentage_error(self.y_true, self.y_pred)
        return {"MAE": mae, "MSE": mse, "MAPE": mape}
