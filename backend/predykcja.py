import pandas as pd
import numpy as np
import requests
import sys
import os
import time
from opencage.geocoder import OpenCageGeocode

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
from model import model_normal, model_out
import re
import json
import ast


with open(os.path.join(BASE_DIR, "metro_stacje.geojson")) as f:
    metro_data = json.load(f)

metro_coords = np.array([
    (feature["geometry"]["coordinates"][1], feature["geometry"]["coordinates"][0])
    for feature in metro_data["features"]
])

# wczytanie danych
df = pd.read_csv(os.path.join(BASE_DIR, "transactions_ready.csv"))  # musi zawierać kolumnę 'coordinates'

# utwórz kolumnę numeryczną dla funkcji budynku
df["przewazajacaFunkcjaBudynku_num"] = df["przewazajacaFunkcjaBudynku"].apply(
    lambda x: 0 if x=="budynek jednorodzinny" else 1
)

df['numer'] = df['numer'].str.replace(",", "-")


# funkcja do pobrania współrzędnych przez OSM
import requests
import time


GEOCODER = OpenCageGeocode("f754d68b43ee405887939e2ab97c1341")

def get_coords(ulica, numer):
    query = f"{ulica} {numer}, Warszawa, Polska"

    try:
        result = GEOCODER.geocode(query)

        if result and len(result):
            lat = result[0]["geometry"]["lat"]
            lng = result[0]["geometry"]["lng"]
            return (lat, lng)

    except Exception as e:
        print("GEOCODING ERROR:", e)

    return None


def numer_to_float(numer):
    m = re.match(r"(\d+)([A-Za-z]*)", str(numer))
    if m:
        base = int(m.group(1))
        suffix = m.group(2)
        if suffix:
            return base + (ord(suffix.lower())-96)/100
        return float(base)
    return np.nan


def find_two_nearest_buildings(ulica, numer):

    target = numer_to_float(numer)

    street_df = df[df["ulica"] == ulica].copy()

    street_df["numer_float"] = street_df["numer"].apply(numer_to_float)

    street_df["diff"] = abs(street_df["numer_float"] - target)

    # filtr: max różnica 5
    street_df = street_df[street_df["diff"] <= 5]

    if len(street_df) == 0:
        return None

    nearest = street_df.nsmallest(2, "diff")

    return nearest



def find_nearest_transactions_by_coords(lat, lon, max_dist = 500, used_buildings = None):
    if used_buildings is None:
        used_buildings = set()

    coords = df["coordinates"].apply(ast.literal_eval)
    latitudes = coords.apply(lambda x: x[0])
    longitudes = coords.apply(lambda x: x[1])

    distances = np.sqrt((latitudes - lat)**2 + (longitudes - lon)**2) * 111000

    df_copy = df.copy()
    df_copy["dist"] = distances
    df_copy["building_id"] = df_copy["ulica"].astype(str) + "_" + df_copy["numer"].astype(str)

    # filtr po max_dist
    nearest = df_copy[df_copy["dist"] <= max_dist]

    # filtruj już użyte budynki
    nearest = nearest[~nearest["building_id"].isin(used_buildings)]

    if nearest.empty:
        return None, used_buildings

    # wybierz k najbliższych
    selected = nearest

    # dodaj wybrane do użytych
    used_buildings.update(selected["building_id"].tolist())

    return selected







def find_nearest_buildings_by_coords(lat, lon, k=5, max_dist=1000, used_buildings=None):
    if used_buildings is None:
        used_buildings = set()

    coords = df["coordinates"].apply(ast.literal_eval)
    latitudes = coords.apply(lambda x: x[0])
    longitudes = coords.apply(lambda x: x[1])

    distances = np.sqrt((latitudes - lat)**2 + (longitudes - lon)**2) * 111000

    df_copy = df.copy()
    df_copy["dist"] = distances
    df_copy["building_id"] = df_copy["ulica"].astype(str) + "_" + df_copy["numer"].astype(str)

    # filtr po max_dist
    nearest = df_copy[df_copy["dist"] <= max_dist]

    # filtruj już użyte budynki
    nearest = nearest[~nearest["building_id"].isin(used_buildings)]

    if nearest.empty:
        return None, used_buildings

    # usuń duplikaty po building_id, zostawiając najbliższy wiersz
    nearest = nearest.sort_values("dist").drop_duplicates("building_id", keep="first")

    # wybierz k najbliższych
    selected = nearest.head(k)

    # dodaj wybrane do użytych
    used_buildings.update(selected["building_id"].tolist())

    return  (selected['srednia_budynek'].mean(), selected['srednia_cena_ulica'].mean(),
            selected['srednia_cena_dzielnica'].mean(), selected['near_100'].values[0],
            selected['near_300'].values[0], np.floor(selected['liczbaKondygnacji'].mean()),
             selected['przewazajacaFunkcjaBudynku'].values[0], selected['near_500'].values[0]
            )



def format_price(series):
    return (
        series
        .round()
        .astype(int)
        .apply(lambda x: f"{x:,}".replace(",", " ") + " zł")
    )


def format_meters(series):
    return (
        series
        .round()
        .astype(int)
        .apply(lambda x: f"{x:,}".replace(",", " ") + " m")
    )







def predict_price(ulica, numer, powierzchnia, piętro, liczba_pokoi):
    if ulica in df["ulica"].values:
        print("Ulica w bazie danych")

        df_clone = df.copy()
        df_clone = df_clone.drop(columns=['Unnamed: 0', 'nr_lokalu', 'liczbaKondygnacji', 'przewazajacaFunkcjaBudynku_num', 'rok'])
        df_clone = df_clone[['ulica', 'numer', 'powierzchnia_uzyt', 'piętro', 'liczba_pokoi', 'cena_za_m2', 'srednia_cena_ulica', 'near_100', 'near_300', 'near_500', 'srednia_cena_dzielnica', 'srednia_budynek', 'dist_centrum', 'dist_metro']]



        if ((df["ulica"] == ulica) & (df["numer"] == numer)).any():
            print("Numer również w bazie danych")

            df_danedowyrdukubudynek = df_clone[(df_clone["ulica"] == ulica) & (df_clone["numer"] == numer)]
            df_danedowyrdukubudynek.loc[:, "near_100"] = int(df.loc[
                                                                 (df['ulica'] == ulica) & (df['numer'] == numer),
                                                                 'near_100'
                                                             ].mean())
            df_danedowyrdukubudynek = df_danedowyrdukubudynek.rename(columns={
                "liczba_pokoi": "liczba pokoi",
                "powierzchnia_uzyt": "powierzchnia użytkowa",
                "cena_za_m2": "cena za m2",
                "srednia_cena_ulica": "średnia cena na ulicy",
                "near_100": "średnia cena w promieniu 100m",
                "near_300": "średnia cena w promieniu 300m",
                "near_500": "średnia cena w promieniu 500m",
                "srednia_cena_dzielnica": "średnia cena w dzielnicy",
                "srednia_budynek": "srednia cena w budynku",
                "dist_centrum": "dystans do centrum",
                "dist_metro": "najbliższa stacja metra"
            })

            price_cols = [
                "cena za m2",
                "średnia cena na ulicy",
                "średnia cena w promieniu 100m",
                "średnia cena w promieniu 300m",
                "średnia cena w promieniu 500m",
                "średnia cena w dzielnicy",
                "srednia cena w budynku"
            ]

            for col in price_cols:
                df_danedowyrdukubudynek[col] = format_price(df_danedowyrdukubudynek[col])

            df_danedowyrdukubudynek["dystans do centrum"] = format_meters(df_danedowyrdukubudynek['dystans do centrum'])

            df_danedowyrdukubudynek["najbliższa stacja metra"] = format_meters(
                df_danedowyrdukubudynek['najbliższa stacja metra'])
            df_danedowyrdukubudynek["powierzchnia użytkowa"] = df_danedowyrdukubudynek["powierzchnia użytkowa"].round().astype(int).apply(lambda x: f"{x:,}".replace(",", " ") + " m2")



            df_danedowyrdukuulica = df_clone[(df_clone["ulica"] == ulica) & (df_clone["numer"] != numer)]
            df_danedowyrdukuulica = df_danedowyrdukuulica.rename(columns={
                "liczba_pokoi": "liczba pokoi",

                "powierzchnia_uzyt": "powierzchnia użytkowa",
                "cena_za_m2": "cena za m2",
                "srednia_cena_ulica": "średnia cena na ulicy",
                "near_100": "średnia cena w promieniu 100m",
                "near_300": "średnia cena w promieniu 300m",
                "near_500": "średnia cena w promieniu 500m",
                "srednia_cena_dzielnica": "średnia cena w dzielnicy",
                "srednia_budynek": "srednia cena w budynku",
                "dist_centrum": "dystans do centrum",
                "dist_metro": "najbliższa stacja metra"
            })

            for col in price_cols:
                df_danedowyrdukuulica[col] = format_price(df_danedowyrdukuulica[col])

            df_danedowyrdukuulica["dystans do centrum"] = format_meters(df_danedowyrdukuulica['dystans do centrum'])
            df_danedowyrdukuulica["najbliższa stacja metra"] = format_meters(
                df_danedowyrdukuulica['najbliższa stacja metra'])
            df_danedowyrdukuulica["powierzchnia użytkowa"] = df_danedowyrdukuulica["powierzchnia użytkowa"].round().astype(int).apply(lambda x: f"{x:,}".replace(",", " ") + " m2")


            coords = get_coords(f"{ulica} {numer}")
            nearest_transactions = find_nearest_transactions_by_coords(coords[0], coords[1])



            nearest_transactions = nearest_transactions[~((nearest_transactions['ulica'] == ulica) & (nearest_transactions['numer'] == numer))]
            df_danedowydrukowanianajblizszaokolica = nearest_transactions.sort_values(by=['dist']).head(35)
            df_danedowydrukowanianajblizszaokolica = df_danedowydrukowanianajblizszaokolica[['ulica', 'numer','dist', 'powierzchnia_uzyt', 'piętro', 'liczba_pokoi', 'cena_za_m2', 'srednia_cena_ulica', 'near_100', 'near_300', 'near_500', 'srednia_cena_dzielnica', 'srednia_budynek', 'dist_centrum', 'dist_metro']]
            df_danedowydrukowanianajblizszaokolica = df_danedowydrukowanianajblizszaokolica.rename(columns={
            "liczba_pokoi": "liczba pokoi",
            "dist": "dystans",
            "powierzchnia_uzyt": "powierzchnia użytkowa",
            "cena_za_m2": "cena za m2",
            "srednia_cena_ulica": "średnia cena na ulicy",
            "near_100": "średnia cena w promieniu 100m",
            "near_300": "średnia cena w promieniu 300m",
            "near_500": "średnia cena w promieniu 500m",
            "srednia_cena_dzielnica": "średnia cena w dzielnicy",
            "srednia_budynek": "srednia cena w budynku",
            "dist_centrum": "dystans do centrum",
            "dist_metro": "najbliższa stacja metra"
            })

            for col in price_cols:
                df_danedowydrukowanianajblizszaokolica[col] = format_price(df_danedowydrukowanianajblizszaokolica[col])

            df_danedowydrukowanianajblizszaokolica["dystans do centrum"] = format_meters(df_danedowydrukowanianajblizszaokolica['dystans do centrum'])
            df_danedowydrukowanianajblizszaokolica["najbliższa stacja metra"] = format_meters(df_danedowydrukowanianajblizszaokolica['najbliższa stacja metra'])
            df_danedowydrukowanianajblizszaokolica["dystans"] = df_danedowydrukowanianajblizszaokolica["dystans"].round().astype(int).apply(lambda x: f"{x:,}".replace(",", " ") + " m")
            df_danedowydrukowanianajblizszaokolica["powierzchnia użytkowa"] = df_danedowydrukowanianajblizszaokolica["powierzchnia użytkowa"].round().astype(int).apply(lambda x: f"{x:,}".replace(",", " ") + " m2")



            budynek_mask = (df["ulica"] == ulica) & (df["numer"] == numer)

            srednia_budynek = df.loc[budynek_mask, "srednia_budynek"].values[0]
            dist_centrum = df.loc[budynek_mask, "dist_centrum"].values[0]
            dist_metro = df.loc[budynek_mask, "dist_metro"].values[0]
            liczbaKondygnacji = df.loc[budynek_mask, "liczbaKondygnacji"].values[0]
            przewazajacaFunkcjaBudynku_num = df.loc[budynek_mask, "przewazajacaFunkcjaBudynku_num"].values[0]
            srednia_cena_dzielnica = df.loc[budynek_mask, "srednia_cena_dzielnica"].values[0]
            near_100 = df.loc[budynek_mask, "near_100"].mean()
            near_300 = df.loc[budynek_mask, "near_300"].values[0]
            near_500 = df.loc[budynek_mask, "near_500"].values[0]
            srednia_ulicy = df.loc[budynek_mask, "srednia_cena_ulica"].values[0]


            # tutaj liczysz cechy wejściowe dla modelu
            inv_powierzchnia = 1 / powierzchnia
            pokoje_na_m2 = liczba_pokoi / powierzchnia
            ulica_vs_budynek = df.loc[budynek_mask, "srednia_cena_ulica"].values[0] - srednia_budynek
            pietro_kondygnacja = piętro / liczbaKondygnacji
            near_diff = near_300 - srednia_budynek
            X_input = pd.DataFrame([{
                "inv_powierzchnia": inv_powierzchnia,
                "liczba_pokoi": liczba_pokoi,
                "piętro": piętro,
                "srednia_cena_dzielnica": srednia_cena_dzielnica,
                # "srednia_cena_ulica",
                "ulica_vs_budynek": ulica_vs_budynek,
                # "near_300",
                "near_diff": near_diff,
                "pokoje_na_m2": pokoje_na_m2,
                "srednia_budynek": srednia_budynek,
                # "relacja_ulica",
                "pietro_kondygnacja": pietro_kondygnacja,
                "przewazajacaFunkcjaBudynku_num": przewazajacaFunkcjaBudynku_num,
                "dist_centrum": dist_centrum,
                "dist_metro": dist_metro
            }])

            if srednia_budynek > np.percentile(df['cena_za_m2'], 97):
                pred = model_out.predict(X_input)[0]
            else:
                pred = model_normal.predict(X_input)[0]

            return {
                "ulica": ulica,
                "numer": numer,
                "powierzchnia użytkowa": f"{powierzchnia} m2",
                "piętro": piętro,
                "liczba pokoi": liczba_pokoi,
                "przewidywana cena": f"{pred.round().astype(int):,}".replace(',', ' ') + " zł",
                "srednia cena w budynku": f"{srednia_budynek.round():,}".replace(',', ' ') + " zł",
                "średnia cena na ulicy": f"{srednia_ulicy.round().astype(int):,}".replace(',', ' ') + " zł",
                "średnia cena w promieniu 100m": f"{near_100.round().astype(int):,}".replace(',', ' ') + " zł",
                "średnia cena w promieniu 300m": f"{near_300.round().astype(int):,}".replace(',', ' ') + " zł",
                "średnia cena w promieniu 500m": f"{near_500.round().astype(int):,}".replace(',', ' ') + " zł",
                "średnia cena w dzielnicy": f"{srednia_cena_dzielnica.round().astype(int):,}".replace(',', ' ') + " zł",
                "dystans do centrum": f"{dist_centrum.round().astype(int):,}".replace(',', ' ') + " m",
                "najbliższa stacja metra": f"{dist_metro.round().astype(int):,}".replace(',', ' ') + " m"
                }, df_danedowydrukowanianajblizszaokolica, df_danedowyrdukuulica, df_danedowyrdukubudynek
        else:
            # przypadek 2: ulica znana, numer nieznany
            print("Brak numeru w bazie danych")
            df_danedowydrukuulica = df[df["ulica"] == ulica]
            df_danedowydrukuulica = df_danedowydrukuulica[['ulica', 'numer','powierzchnia_uzyt','piętro', 'liczba_pokoi', 'cena_za_m2', 'srednia_cena_ulica', 'near_100', 'near_300', 'near_500', 'srednia_cena_dzielnica', 'srednia_budynek', 'dist_centrum', 'dist_metro']]
            df_danedowydrukuulica = df_danedowydrukuulica.rename(columns={
            "liczba_pokoi": "liczba pokoi",
            "powierzchnia_uzyt": "powierzchnia użytkowa",
            "cena_za_m2": "cena za m2",
            "srednia_cena_ulica": "średnia cena na ulicy",
            "near_100": "średnia cena w promieniu 100m",
            "near_300": "średnia cena w promieniu 300m",
            "near_500": "średnia cena w promieniu 500m",
            "srednia_cena_dzielnica": "średnia cena w dzielnicy",
            "srednia_budynek": "srednia cena w budynku",
            "dist_centrum": "dystans do centrum",
            "dist_metro": "najbliższa stacja metra"
            })

            price_cols = [
                "cena za m2",
                "średnia cena na ulicy",
                "średnia cena w promieniu 100m",
                "średnia cena w promieniu 300m",
                "średnia cena w promieniu 500m",
                "średnia cena w dzielnicy",
                "srednia cena w budynku"
            ]

            for col in price_cols:
                df_danedowydrukuulica[col] = format_price(df_danedowydrukuulica[col])

            df_danedowydrukuulica["dystans do centrum"] = format_meters(df_danedowydrukuulica['dystans do centrum'])
            df_danedowydrukuulica["najbliższa stacja metra"] = format_meters(df_danedowydrukuulica['najbliższa stacja metra'])
            df_danedowydrukuulica["powierzchnia użytkowa"] = df_danedowydrukuulica["powierzchnia użytkowa"].round().astype(int).apply(lambda x: f"{x:,}".replace(",", " ") + " m2")


            coords = get_coords(f"{ulica} {numer}")
            if coords is not None:
                lat, lon = coords

                # odległości od centrum i metra
                pk_latlon = (52.2319581, 21.0067249)
                dist_centrum = np.sqrt((lat - pk_latlon[0]) ** 2 + (lon - pk_latlon[1]) ** 2) * 111000
                dist_metro = np.min(np.sqrt((metro_coords[:, 0] - lat) ** 2 + (metro_coords[:, 1] - lon) ** 2) * 111000)


                # znajdź 2 najbliższych budynków na ulicy
                nearest_buildings = find_two_nearest_buildings(ulica, numer)
                if nearest_buildings is not None:
                    srednia_sasiadow = nearest_buildings["srednia_budynek"].mean()
                    srednia_ulicy = df[df["ulica"] == ulica]["srednia_cena_ulica"].mean()
                    # dzielnica z najbliższego sąsiada
                    najblizsza_dzielnica = nearest_buildings.iloc[0]["dzielnica"]
                    srednia_dzielnicy = df[df["dzielnica"] == najblizsza_dzielnica]["srednia_cena_dzielnica"].mean()
                    nearest = nearest_buildings.iloc[0]  # najbliższy numer
                    near_100 = nearest["near_100"]
                    near_300 = nearest["near_300"]
                    near_500 = nearest["near_500"]
                    # średnia arytmetyczna
                    srednia_budynek = np.mean([srednia_sasiadow, srednia_ulicy, srednia_dzielnicy, near_300])


                else:
                    # jeśli brak sąsiadów, bierzemy średnią ulicy i dzielnicy
                    near_100 = df[df["ulica"] == ulica]["near_100"].mean()
                    near_300 = df[df["ulica"] == ulica]["near_300"].mean()
                    near_500 = df[df["ulica"] == ulica]["near_500"].mean()
                    srednia_ulicy = df[df["ulica"] == ulica]["srednia_cena_ulica"].mean()
                    srednia_dzielnicy = df["srednia_cena_dzielnica"].mean()
                    srednia_budynek = np.mean([srednia_ulicy, srednia_dzielnicy, near_300])


                # liczba kondygnacji i funkcja budynku: bierzemy z najbliższego sąsiada jeśli jest
                if nearest_buildings is not None:
                    liczbaKondygnacji = nearest_buildings.iloc[0]["liczbaKondygnacji"]
                    przewazajacaFunkcjaBudynku_num = nearest_buildings.iloc[0]["przewazajacaFunkcjaBudynku_num"]
                else:
                    liczbaKondygnacji = df[df["ulica"] == ulica]["liczbaKondygnacji"].mean()
                    przewazajacaFunkcjaBudynku_num = df[df["ulica"] == ulica]["przewazajacaFunkcjaBudynku_num"].mode()[
                        0]

                # cechy wejściowe do modelu
                inv_powierzchnia = 1 / powierzchnia
                pokoje_na_m2 = liczba_pokoi / powierzchnia
                ulica_vs_budynek = df[df["ulica"] == ulica]["srednia_cena_ulica"].mean() - srednia_budynek
                pietro_kondygnacja = piętro / liczbaKondygnacji
                near_diff = near_300 - srednia_budynek

                X_input = pd.DataFrame([{
                    "inv_powierzchnia": inv_powierzchnia,
                    "liczba_pokoi": liczba_pokoi,
                    "piętro": piętro,
                    "srednia_cena_dzielnica": srednia_dzielnicy,
                    "ulica_vs_budynek": ulica_vs_budynek,
                    "near_diff": near_diff,
                    "pokoje_na_m2": pokoje_na_m2,
                    "srednia_budynek": srednia_budynek,
                    "pietro_kondygnacja": pietro_kondygnacja,
                    "przewazajacaFunkcjaBudynku_num": przewazajacaFunkcjaBudynku_num,
                    "dist_centrum": dist_centrum,
                    "dist_metro": dist_metro
                }])

                if srednia_budynek > np.percentile(df['cena_za_m2'], 97):
                    pred = model_out.predict(X_input)[0]
                else:
                    pred = model_normal.predict(X_input)[0]
            else:
                print("Błedny adres")
                raise ValueError(f"Nieprawidłowy adres: {ulica} {numer}")

            nearest_transactions = find_nearest_transactions_by_coords(coords[0], coords[1])
            df_danedowydrukowanianajblizszaokolica = nearest_transactions.sort_values(by=['dist']).head(35)
            df_danedowydrukowanianajblizszaokolica = df_danedowydrukowanianajblizszaokolica[['ulica', 'numer', 'dist', 'powierzchnia_uzyt', 'piętro', 'liczba_pokoi', 'cena_za_m2', 'srednia_cena_ulica', 'near_100', 'near_300', 'near_500', 'srednia_cena_dzielnica', 'srednia_budynek', 'dist_centrum', 'dist_metro']]
            df_danedowydrukowanianajblizszaokolica = df_danedowydrukowanianajblizszaokolica.rename(columns={
            "liczba_pokoi": "liczba pokoi",
            "dist": "dystans",
            "powierzchnia_uzyt": "powierzchnia użytkowa",
            "cena_za_m2": "cena za m2",
            "srednia_cena_ulica": "średnia cena na ulicy",
            "near_100": "średnia cena w promieniu 100m",
            "near_300": "średnia cena w promieniu 300m",
            "near_500": "średnia cena w promieniu 500m",
            "srednia_cena_dzielnica": "średnia cena w dzielnicy",
            "srednia_budynek": "srednia cena w budynku",
            "dist_centrum": "dystans do centrum",
            "dist_metro": "najbliższa stacja metra"
            })

            for col in price_cols:
                df_danedowydrukowanianajblizszaokolica[col] = format_price(df_danedowydrukowanianajblizszaokolica[col])

            df_danedowydrukowanianajblizszaokolica["dystans do centrum"] = format_meters(df_danedowydrukowanianajblizszaokolica['dystans do centrum'])
            df_danedowydrukowanianajblizszaokolica["najbliższa stacja metra"] = format_meters(df_danedowydrukowanianajblizszaokolica['najbliższa stacja metra'])
            df_danedowydrukowanianajblizszaokolica["dystans"] = df_danedowydrukowanianajblizszaokolica["dystans"].round().astype(int).apply(lambda x: f"{x:,}".replace(",", " ") + " m")
            df_danedowydrukowanianajblizszaokolica["powierzchnia użytkowa"] = df_danedowydrukowanianajblizszaokolica["powierzchnia użytkowa"].round().astype(int).apply(lambda x: f"{x:,}".replace(",", " ") + " m2")


            return {
                "ulica": ulica,
                "numer": numer,
                "powierzchnia użytkowa": f"{powierzchnia} m2",
                "piętro": piętro,
                "liczba pokoi": liczba_pokoi,
                "przewidywana cena": f"{pred.round().astype(int):,}".replace(',', ' ') + " zł",
                "średnia cena na ulicy": f"{srednia_ulicy.round().astype(int):,}".replace(',', ' ') + " zł",
                "średnia cena w promieniu 100m": f"{near_100.round().astype(int):,}".replace(',', ' ') + " zł",
                "średnia cena w promieniu 300m": f"{near_300.round().astype(int):,}".replace(',', ' ') + " zł",
                "średnia cena w promieniu 500m": f"{near_500.round().astype(int):,}".replace(',', ' ') + " zł",
                "średnia cena w dzielnicy": f"{srednia_dzielnicy.round().astype(int):,}".replace(',', ' ') + " zł",
                "srednia przewidywana cena w budynku": f"{srednia_budynek.round():,}".replace(',', ' ') + " zł",
                "dystans do centrum": f"{dist_centrum.round().astype(int):,}".replace(',', ' ') + " m",
                "najbliższa stacja metra": f"{dist_metro.round().astype(int):,}".replace(',', ' ') + " m"
                }, df_danedowydrukowanianajblizszaokolica ,df_danedowydrukuulica




    else:
        print("Ulica nieznana")
        coords = get_coords(f"{ulica} {numer}")
        if coords is not None:
            lat, lon = coords

            # odległości od centrum i metra
            pk_latlon = (52.2319581, 21.0067249)
            dist_centrum = np.sqrt((lat - pk_latlon[0]) ** 2 + (lon - pk_latlon[1]) ** 2) * 111000
            dist_metro = np.min(np.sqrt((metro_coords[:, 0] - lat) ** 2 + (metro_coords[:, 1] - lon) ** 2) * 111000)

            y = find_nearest_buildings_by_coords(lat, lon)

            srednia_budynek = (y[0] + y[3])/2
            srednia_cena_ulica = y[1]
            srednia_cena_dzielnica = y[2]
            near_100 = y[3]
            near_300 = y[4]
            inv_powierzchnia = 1 / powierzchnia
            pokoje_na_m2 = liczba_pokoi / powierzchnia
            ulica_vs_budynek = srednia_cena_ulica - srednia_budynek
            liczbaKondygnacji = y[5]
            przewazajacaFunkcjaBudynku_num = 0 if y[6]=="budynek jednorodzinny" else 1
            near_diff = near_300 - srednia_budynek
            pietro_kondygnacja = piętro / liczbaKondygnacji
            near_500 = y[7]

            X_input = pd.DataFrame([{
                "inv_powierzchnia": inv_powierzchnia,
                "liczba_pokoi": liczba_pokoi,
                "piętro": piętro,
                "srednia_cena_dzielnica": srednia_cena_dzielnica,
                "ulica_vs_budynek": ulica_vs_budynek,
                "near_diff": near_diff,
                "pokoje_na_m2": pokoje_na_m2,
                "srednia_budynek": srednia_budynek,
                "pietro_kondygnacja": pietro_kondygnacja,
                "przewazajacaFunkcjaBudynku_num": przewazajacaFunkcjaBudynku_num,
                "dist_centrum": dist_centrum,
                "dist_metro": dist_metro
            }])

            if srednia_budynek > np.percentile(df['cena_za_m2'], 97):
                pred = model_out.predict(X_input)[0]
            else:
                pred = model_normal.predict(X_input)[0]
        else:
            raise ValueError(f"Nieprawidłowy adres: {ulica} {numer}")


        nearest_transactions = find_nearest_transactions_by_coords(coords[0], coords[1])
        df_danedowydrukowanianajblizszaokolica = nearest_transactions.sort_values(by=['dist']).head(35)
        df_danedowydrukowanianajblizszaokolica = df_danedowydrukowanianajblizszaokolica[['ulica', 'numer', 'dist', 'powierzchnia_uzyt', 'piętro', 'liczba_pokoi', 'cena_za_m2', 'srednia_cena_ulica', 'near_100', 'near_300', 'near_500', 'srednia_cena_dzielnica', 'srednia_budynek', 'dist_centrum', 'dist_metro']]
        df_danedowydrukowanianajblizszaokolica = df_danedowydrukowanianajblizszaokolica.rename(columns={
            "liczba_pokoi": "liczba pokoi",
            "dist": "dystans",
            "powierzchnia_uzyt": "powierzchnia użytkowa",
            "cena_za_m2": "cena za m2",
            "srednia_cena_ulica": "średnia cena na ulicy",
            "near_100": "średnia cena w promieniu 100m",
            "near_300": "średnia cena w promieniu 300m",
            "near_500": "średnia cena w promieniu 500m",
            "srednia_cena_dzielnica": "średnia cena w dzielnicy",
            "srednia_budynek": "srednia cena w budynku",
            "dist_centrum": "dystans do centrum",
            "dist_metro": "najbliższa stacja metra"
        })
        price_cols = [
            "cena za m2",
            "średnia cena na ulicy",
            "średnia cena w promieniu 100m",
            "średnia cena w promieniu 300m",
            "średnia cena w promieniu 500m",
            "średnia cena w dzielnicy",
            "srednia cena w budynku"
        ]


        for col in price_cols:
            df_danedowydrukowanianajblizszaokolica[col] = format_price(df_danedowydrukowanianajblizszaokolica[col])

        df_danedowydrukowanianajblizszaokolica["dystans do centrum"] = format_meters(df_danedowydrukowanianajblizszaokolica['dystans do centrum'])
        df_danedowydrukowanianajblizszaokolica["najbliższa stacja metra"] = format_meters(df_danedowydrukowanianajblizszaokolica['najbliższa stacja metra'])
        df_danedowydrukowanianajblizszaokolica["dystans"] = df_danedowydrukowanianajblizszaokolica["dystans"].round().astype(int).apply(lambda x: f"{x:,}".replace(",", " ") + " m")
        df_danedowydrukowanianajblizszaokolica["powierzchnia użytkowa"] = df_danedowydrukowanianajblizszaokolica["powierzchnia użytkowa"].round().astype(int).apply(lambda x: f"{x:,}".replace(",", " ") + " m2")

        return {
            "ulica": ulica,
            "numer": numer,
            "powierzchnia użytkowa": f"{powierzchnia} m2",
            "piętro": piętro,
            "liczba pokoi": liczba_pokoi,
            "przewidywana cena": f"{pred.round().astype(int):,}".replace(',', ' ') + " zł",
            "średnia cena w promieniu 100m": f"{near_100.round().astype(int):,}".replace(',', ' ') + " zł",
            "średnia cena w promieniu 300m": f"{near_300.round().astype(int):,}".replace(',', ' ') + " zł",
            "średnia cena w promieniu 500m": f"{near_500.round().astype(int):,}".replace(',', ' ') + " zł",
            "średnia cena w dzielnicy": f"{srednia_cena_dzielnica.round().astype(int):,}".replace(',', ' ') + " zł",
            "średnia przewidywana cena w budynku": f"{srednia_budynek.round().astype(int):,}".replace(',', ' ') + " zł",
            "średnia przewidywana cena na ulicy": f"{srednia_cena_ulica.round().astype(int):,}".replace(',',' ') + " zł",
            "dystans do centrum": f"{dist_centrum.round().astype(int):,}".replace(',', ' ') + " m",
            "najbliższa stacja metra": f"{dist_metro.round().astype(int):,}".replace(',', ' ') + " m"
        }, df_danedowydrukowanianajblizszaokolica











if __name__ == "__main__":

    record = predict_price("Pala Telekiego", "12", 41, 1, 1)


    df_result = pd.DataFrame([record[0]])
    df_result.to_csv("predykcja.csv", index=False)
    print("Zapisano do predykcja.csv")


    df_danenajblizszaokolica = record[1]
    df_danenajblizszaokolica.to_csv("dane z najblizszej okolicy.csv")
    print("Zapisano do dane z najblizszej okolicy.csv")


    if(len(record) >= 3):
        df_daneulica = record[2]
        df_daneulica.to_csv("dane z ulicy.csv")
        print("Zapisano do dane z ulicy.csv")

    if(len(record) >= 4):
        df_danebudynek = record[3]
        df_danebudynek.to_csv("dane z budynku.csv")
        print("Zapisano do dane z budynku.csv")


