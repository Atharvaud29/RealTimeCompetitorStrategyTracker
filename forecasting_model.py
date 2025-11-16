import pandas as pd
import numpy as np
from sklearn.preprocessing import RobustScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import matplotlib.pyplot as plt

# ================================================================
# 1. LOAD DATA
# ================================================================
df = pd.read_csv("samsung-galaxy-s24-5g-ai-smartphone-marble-gray-8gb-128gb-storage_amazon_price_history.csv")

df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date")

prices = df["price"].values.reshape(-1, 1)

# ================================================================
# 2. SCALING
# ================================================================
scaler = RobustScaler()
scaled_prices = scaler.fit_transform(prices)

# ================================================================
# 3. CREATE WINDOWED SEQUENCE DATA
# ================================================================
window = 3  # SMALL DATA → small window

X, y = [], []
for i in range(window, len(scaled_prices)):
    X.append(scaled_prices[i-window:i, 0])
    y.append(scaled_prices[i, 0])

X, y = np.array(X), np.array(y)
X = X.reshape((X.shape[0], X.shape[1], 1))

# ================================================================
# 4. TRAIN-TEST SPLIT (80% TRAIN, 20% TEST)
# ================================================================
split_idx = int(len(X) * 0.8)
X_train, X_test = X[:split_idx], X[split_idx:]
y_train, y_test = y[:split_idx], y[split_idx:]

# ================================================================
# 5. SIMPLE LSTM MODEL (SUITABLE FOR TINY DATASET)
# ================================================================
model = Sequential([
    LSTM(32, return_sequences=False, input_shape=(window, 1)),
    Dropout(0.2),
    Dense(16, activation="relu"),
    Dense(1)
])

model.compile(optimizer="adam", loss="mse")

model.fit(X_train, y_train, epochs=100, batch_size=4, verbose=1)

# ================================================================
# 6. PREDICTIONS
# ================================================================
pred_scaled = model.predict(X_test)
pred_prices = scaler.inverse_transform(pred_scaled.reshape(-1, 1))
actual_prices = scaler.inverse_transform(y_test.reshape(-1, 1))

# ================================================================
# FUTURE FORECAST (Next 30 Days + 10% Increase)
# ================================================================
future_steps = 30   # 30-day forecast
increase_factor = 1.10  # 10% price increase

last_seq = scaled_prices[-window:].reshape(1, window, 1)
future_scaled = []

for _ in range(future_steps):
    next_pred_scaled = model.predict(last_seq, verbose=0)[0][0]

    # Save scaled prediction
    future_scaled.append(next_pred_scaled)

    # Update sequence for next prediction
    last_seq = np.append(last_seq[:, 1:, :], [[[next_pred_scaled]]], axis=1)

# Convert scaled → actual prices
future_prices = scaler.inverse_transform(np.array(future_scaled).reshape(-1, 1))

# Apply 10% increase to future forecast
future_prices = future_prices * increase_factor

# Generate future dates
future_dates = pd.date_range(start=df["date"].max() + pd.Timedelta(days=1), periods=future_steps)

forecast_df = pd.DataFrame({
    "date": future_dates,
    "forecast_price": future_prices.flatten()
})


# ================================================================
# 8. PLOT
# ================================================================
plt.figure(figsize=(12, 6))
plt.plot(df["date"][window:], scaler.inverse_transform(scaled_prices[window:]), label="Actual Price", linewidth=2)
plt.plot(df["date"].iloc[window + split_idx:], pred_prices, label="Predicted Price", linewidth=2)
plt.plot(future_dates, future_prices, label="Future Forecast", linewidth=2)

plt.title("Actual vs Predicted vs Forecasted Prices")
plt.xlabel("Date")
plt.ylabel("Price")
plt.legend()
plt.grid(True)
plt.show()

# ================================================================
# 9. METRICS
# ================================================================
mse = mean_squared_error(actual_prices, pred_prices)
mae = mean_absolute_error(actual_prices, pred_prices)
rmse = np.sqrt(mse)
r2 = r2_score(actual_prices, pred_prices)

print("\n----- Model Evaluation -----")
print(f"MSE  : {mse:.2f}")
print(f"MAE  : {mae:.2f}")
print(f"RMSE : {rmse:.2f}")
print(f"R²   : {r2:.4f}")
