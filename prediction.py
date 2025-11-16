import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from sklearn.preprocessing import RobustScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, Bidirectional
# from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import matplotlib.pyplot as plt


# Load your scraped dataset
df = pd.read_csv("samsung-galaxy-s24-5g-ai-smartphone-marble-gray-8gb-128gb-storage_amazon_price_history.csv")

# Ensure chronological order
df = df.sort_values("date")
df['date'] = pd.to_datetime(df['date'])
prices = df['price'].values.reshape(-1, 1)

# Normalize data
#scaler = MinMaxScaler(feature_range=(0, 1))
scaler = RobustScaler()
scaled_prices = scaler.fit_transform(prices)


# Prepare data for LSTM
X, y = [], []
window = 15  # lookback window size
for i in range(window, len(scaled_prices)):
    X.append(scaled_prices[i-window:i, 0])
    y.append(scaled_prices[i, 0])
X, y = np.array(X), np.array(y)
X = np.reshape(X, (X.shape[0], X.shape[1], 1))

# 4. Build improved Bidirectional LSTM model
model = Sequential([
    Bidirectional(LSTM(128, return_sequences=True), input_shape=(X.shape[1], 1)),
    Dropout(0.3),
    Bidirectional(LSTM(64, return_sequences=True)),
    Dropout(0.2),
    LSTM(32),
    Dense(64, activation='relu'),
    Dense(1)
])

model.compile(optimizer='adam', loss='mean_squared_error')

# 5. Add callbacks for better training control
# early_stop = EarlyStopping(monitor='loss', patience=15, restore_best_weights=True)
# reduce_lr = ReduceLROnPlateau(monitor='loss', factor=0.5, patience=10, verbose=1)

# 6. Train
history = model.fit(
    X, y,
    epochs=200,
    batch_size=15,
    verbose=1,
    #callbacks=[early_stop, reduce_lr]
)

# 7. Predict
predicted = model.predict(X)
predicted_prices = scaler.inverse_transform(predicted)
actual_prices = scaler.inverse_transform(y.reshape(-1, 1))

# 6. Future Forecast (Next 7 Days)
future_steps = 7
last_sequence = X[-1]
future_predictions = []

for _ in range(future_steps):
    last_sequence_reshaped = np.reshape(last_sequence, (1, last_sequence.shape[0], 1))
    next_pred_scaled = model.predict(last_sequence_reshaped, verbose=0)
    future_predictions.append(next_pred_scaled[0, 0])
    last_sequence = np.append(last_sequence[1:], next_pred_scaled[0, 0])

future_prices = scaler.inverse_transform(np.array(future_predictions).reshape(-1, 1))

# Future dates
last_date = df["date"].max()
future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=future_steps)
forecast_df = pd.DataFrame({
    "date": future_dates,
    "forecast_price": future_prices.flatten()
})


# 8. Plot
plt.figure(figsize=(12,6))
plt.plot(df["date"].iloc[window:], actual_prices, label="Actual Prices", color='blue', linewidth=2)
plt.plot(df["date"].iloc[window:], predicted_prices, label="Predicted Prices", color='red', linewidth=2)
plt.plot(forecast_df["date"], forecast_df["forecast_price"], label="Forecasted Future Prices", color='green', linewidth=2)

plt.title("Actual vs Predicted vs Future Forecast (Bidirectional LSTM)")
plt.xlabel("Date")
plt.ylabel("Price")
plt.legend()
plt.grid(True)
plt.show()


# 9. Evaluate
y_true = np.ravel(actual_prices)
y_pred = np.ravel(predicted_prices)
mse = mean_squared_error(y_true, y_pred)
mae = mean_absolute_error(y_true, y_pred)
rmse = np.sqrt(mse)
r2 = r2_score(y_true, y_pred)

print("\n----- Model Evaluation Metrics -----")
print(f"MSE  : {mse:.2f}")
print(f"MAE  : {mae:.2f}")
print(f"RMSE : {rmse:.2f}")
print(f"R²   : {r2:.4f}")
