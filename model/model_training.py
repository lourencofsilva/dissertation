"""
This module contains the ModelTrainer class, which is responsible for training the model.
"""

import json

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping
import keras_tuner as kt


class ModelTrainer:
    def __init__(self, model_type="LSTM"):
        self.model_type = model_type
        self.data_shape = None

    def build_ffnn(self, hp):
        model = Sequential()

        model.add(Input(shape=(self.data_shape[1],)))

        # Input Layer
        model.add(Dense(hp.Choice('units_input', [64, 128, 256]),
                        activation=hp.Choice('activation', ['relu', 'tanh'])))
        model.add(Dropout(hp.Float('dropout_input', 0.1, 0.3, step=0.1)))

        # Hidden Layers
        for i in range(hp.Int('num_layers', 2, 4)):
            model.add(Dense(hp.Choice(f'units_{i}', [64, 128, 256]),
                            activation=hp.Choice('activation', ['relu', 'tanh'])))
            model.add(Dropout(hp.Float(f'dropout_{i}', 0.1, 0.3, step=0.1)))

        # Output Layer
        model.add(Dense(1))

        model.compile(optimizer=hp.Choice('optimizer', ['adam', 'rmsprop']), loss='mse')
        return model

    def train_ffnn(self, X_train, y_train):
        self.data_shape = X_train.shape

        tuner = kt.RandomSearch(
            self.build_ffnn,
            objective='val_loss',
            max_trials=100,
            executions_per_trial=1,
            directory='tuner_results',
            project_name='traffic_ffnn'
        )

        early_stopping = EarlyStopping(monitor='val_loss', patience=5, restore_best_weights=True)

        tuner.search(X_train, y_train, epochs=50, batch_size=256, validation_split=0.2, callbacks=
            [early_stopping])

        best_hps = tuner.get_best_hyperparameters(num_trials=1)[0]

        best_hps_dict = best_hps.values
        print(json.dumps(best_hps_dict, indent=4))

        # Save to file
        with open("best_hyperparameters.json", "w") as f:
            json.dump(best_hps_dict, f, indent=4)

        best_model = tuner.hypermodel.build(best_hps)
        best_model.fit(X_train, y_train, epochs=50, batch_size=256, validation_split=0.2, callbacks=[early_stopping])

        return best_model

    def train_lstm(self, X_train, y_train):
        model = Sequential([
            Input(shape=(X_train.shape[1], X_train.shape[2])),

            LSTM(100, return_sequences=True),
            Dropout(0.1),

            LSTM(100),
            Dropout(0.1),

            Dense(1)
        ])

        # Using Adam with a tuned learning rate
        optimizer = Adam(learning_rate=0.001)
        model.compile(optimizer=optimizer, loss='mse')

        early_stopping = EarlyStopping(
            monitor='val_loss',
            patience=5,
            restore_best_weights=True,
            verbose=1
        )

        model.fit(
            X_train,
            y_train,
            epochs=50,
            batch_size=64,
            validation_split=0.2,
            callbacks=[early_stopping]
        )
        return model

    def train_model(self, X_train, y_train):
        if self.model_type == "LSTM":
            return self.train_lstm(X_train, y_train)
        elif self.model_type == "FFNN":
            return self.train_ffnn(X_train, y_train)
