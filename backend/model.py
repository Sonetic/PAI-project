import pandas as pd
import numpy as np
import os
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import sys
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)


# wczytanie
df = pd.read_csv(os.path.join(BASE_DIR, "transactions_ready.csv"))
df["inv_powierzchnia"] = 1/df["powierzchnia_uzyt"]
df["relacja_ulica"] = df["srednia_budynek"] / df["srednia_cena_dzielnica"]
df["pokoje_na_m2"] = df["liczba_pokoi"] / df["powierzchnia_uzyt"]
df["near_diff"] = df["near_300"] - df["srednia_budynek"]
df["ulica_vs_budynek"] = df["srednia_cena_ulica"] - df["srednia_budynek"]
df["przewazajacaFunkcjaBudynku_num"] = df["przewazajacaFunkcjaBudynku"].apply(lambda x: 0 if x=="budynek jednorodzinny" else 1)
df["pietro_kondygnacja"] =  df["piętro"] / df["liczbaKondygnacji"]
df["rodzaj_rynku"] = df["rodzaj_rynku"].apply(lambda x: 0 if x=="wtorny" else 1)


features = [
    "inv_powierzchnia",
    "liczba_pokoi",
    "piętro",
    "srednia_cena_dzielnica",
    #"srednia_cena_ulica",
    "ulica_vs_budynek",
    #"near_300",
    "near_diff",
    "pokoje_na_m2",
    "srednia_budynek",
   # "relacja_ulica",
    "pietro_kondygnacja",
    "przewazajacaFunkcjaBudynku_num",
    "dist_centrum",
    "dist_metro",
    #"rodzaj_rynku"
]



target = "cena_za_m2"

X = df[features]
y = df[target]

# podzial na percentyle
threshold = np.percentile(y, 98)

mask_normal = y <= threshold
mask_outliers = y > threshold

X_normal, y_normal = X[mask_normal], y[mask_normal]
X_out, y_out = X[mask_outliers], y[mask_outliers]

#print(f"Normal: {len(X_normal)}, Outliers: {len(X_out)}")

#split
Xn_train, Xn_test, yn_train, yn_test = train_test_split(
    X_normal, y_normal, test_size=0.2, random_state=42
)

Xo_train, Xo_test, yo_train, yo_test = train_test_split(
    X_out, y_out, test_size=0.2, random_state=42
)

#modele
model_normal = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("scaler", StandardScaler()),
    ("model", Ridge(alpha=1.0))
])

model_out = Pipeline([
    ("imputer", SimpleImputer(strategy="median")),
    ("model", GradientBoostingRegressor(n_estimators=600, max_depth=3, learning_rate=0.01))
])

#trening
model_normal.fit(Xn_train, yn_train)
model_out.fit(Xo_train, yo_train)

# predykcja
yn_pred = model_normal.predict(Xn_test)
yo_pred = model_out.predict(Xo_test)

# train predictions
yn_pred_train = model_normal.predict(Xn_train)
yo_pred_train = model_out.predict(Xo_train)

# metryki
def mape(y_true, y_pred):
    errors = np.abs(y_true - y_pred) / y_pred * 100

    print("<5%:", (errors < 5).mean())
    print("<10%:", (errors < 10).mean())
    print("<15%:", (errors < 15).mean())
    mdape = np.median(errors)

    print("MdAPE:", mdape)


    return np.mean(np.abs((y_true - y_pred) / y_true)) * 100

def print_metrics(name, y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mape_val = mape(y_true, y_pred)

    print(f"\n{name}")
    print(f"MAE:  {mae:.2f}")
    print(f"RMSE: {rmse:.2f}")
    print(f"MAPE: {mape_val:.2f}%")



# policz korelacje między cechami
corr_matrix = df[features].corr()
'''
# wyświetl w formie mapy cieplnej
plt.figure(figsize=(10,8))
sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="coolwarm")
plt.title("Macierz korelacji cech")
#plt.show()
'''
'''
rok:
NORMAL TRAIN (Ridge)
MAE:  1213.13
RMSE: 1743.33
MAPE: 7.62%

NORMAL TEST (Ridge)
MAE:  1204.48
RMSE: 1739.53
MAPE: 7.57%

OUTLIERS TRAIN (GBR)
MAE:  2029.44
RMSE: 2817.12
MAPE: 5.72%

OUTLIERS TEST (GBR)
MAE:  2571.27
RMSE: 3958.39
MAPE: 6.97%
inv_powierzchnia: 462.23
liczba_pokoi: 137.85
piętro: 116.76
srednia_cena_dzielnica: 0.04
ulica_vs_budynek: 20.36
near_diff: 374.10
pokoje_na_m2: -126.41
srednia_budynek: 3150.40
pietro_kondygnacja: 58.28
przewazajacaFunkcjaBudynku_num: -63.97


miesiac:

NORMAL TRAIN (Ridge)
MAE:  1250.82
RMSE: 1771.12
MAPE: 7.86%

NORMAL TEST (Ridge)
MAE:  1243.75
RMSE: 1762.77
MAPE: 7.78%

OUTLIERS TRAIN (GBR)
MAE:  2056.22
RMSE: 2896.28
MAPE: 5.75%

OUTLIERS TEST (GBR)
MAE:  2595.89
RMSE: 4263.42
MAPE: 6.97%
inv_powierzchnia: 484.67
liczba_pokoi: 164.16
piętro: 119.14
srednia_cena_dzielnica: 13.27
ulica_vs_budynek: 24.53
near_diff: 355.34
pokoje_na_m2: -152.14
srednia_budynek: 3100.92
pietro_kondygnacja: 65.58
przewazajacaFunkcjaBudynku_num: -57.43

'''


#  filtr 2025
df_2025 = df[df['rok'] == 2025]

X_2025 = df_2025[features]
y_2025 = df_2025[target]

# podział na percentyle tylko w 2025
threshold_2025 = np.percentile(y_2025, 98)
mask_normal_2025 = y_2025 <= threshold_2025
mask_out_2025 = y_2025 > threshold_2025

X_normal_2025 = X_2025[mask_normal_2025]
y_normal_2025 = y_2025[mask_normal_2025]

X_out_2025 = X_2025[mask_out_2025]
y_out_2025 = y_2025[mask_out_2025]

# predykcja
yn_pred_2025 = model_normal.predict(X_normal_2025)
yo_pred_2025 = model_out.predict(X_out_2025)

'''
# metryki tylko dla 2025
print_metrics("NORMAL TEST 2025 (Ridge)", y_normal_2025, yn_pred_2025)
print_metrics("OUTLIERS TEST 2025 (GBR)", y_out_2025, yo_pred_2025)

print_metrics("NORMAL TRAIN (Ridge)", yn_train, yn_pred_train)
print_metrics("NORMAL TEST (Ridge)", yn_test, yn_pred)

print_metrics("OUTLIERS TRAIN (GBR)", yo_train, yo_pred_train)
print_metrics("OUTLIERS TEST (GBR)", yo_test, yo_pred)


coefs = model_normal.named_steps["model"].coef_

for f, c in zip(features, coefs):
    print(f"{f}: {c:.2f}")



inv_powierzchnia: 474.40
liczba_pokoi: 116.95
piętro: 135.71
srednia_cena_dzielnica: -86.34
ulica_vs_budynek: 6.67
near_diff: 90.31
pokoje_na_m2: -107.72
srednia_budynek: 3378.99
pietro_kondygnacja: 46.37
przewazajacaFunkcjaBudynku_num: -54.24
dist_centrum: 108.50
dist_metro: -37.26


NORMAL TEST 2025 (Ridge)
MAE:  1186.15
RMSE: 1685.68
MAPE: 7.32%
<5%: 0.5543933054393305
<10%: 0.8472803347280334
<15%: 0.9372384937238494
MdAPE: 4.444079272546567


'''