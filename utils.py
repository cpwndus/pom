import pandas as pd
import numpy as np

CENTER_SUPPLY = {
    '서울중앙혈액원': 850, '서울남부혈액원': 580,
    '부산혈액원':     520, '대구경북혈액원': 550,
    '경기혈액원':     500, '광주전남혈액원': 460,
}

def get_stats(df):
    stats = df.groupby('hospital_id')['actual_use'].agg(['mean','std']).reset_index()
    stats.columns = ['hospital_id', 'daily_avg', 'daily_std']
    return stats

def compute_allocation(df, target_date, center=None):
    stats    = get_stats(df)
    day_pred = df[df['date'] == pd.Timestamp(target_date)].copy()
    if day_pred.empty:
        return pd.DataFrame()

    day_pred['predicted'] = day_pred['ma7_pred'].fillna(day_pred['actual_use'])
    day_pred = day_pred.merge(stats, on='hospital_id')

    centers = [center] if center else list(CENTER_SUPPLY.keys())
    results = []

    for c in centers:
        supply    = CENTER_SUPPLY[c]
        hospitals = day_pred[day_pred['blood_center'] == c].copy()
        if len(hospitals) == 0:
            continue

        hospitals['cv'] = hospitals['daily_std'] / hospitals['daily_avg']
        hospitals['sigma_mult'] = hospitals['cv'].apply(
            lambda cv: 1.2 if cv > 0.25 else 0.7 if cv > 0.18 else 0.3
        )
        er_bonus  = hospitals['er_level'].map({'권역': 0.2, '지역': 0.0})
        is_panic  = int(hospitals['is_panic_day'].iloc[0]) if len(hospitals) > 0 else 0
        hospitals['sigma_mult'] = hospitals['sigma_mult'] + er_bonus + (0.5 if is_panic else 0)

        hospitals['slack']      = (hospitals['sigma_mult'] * hospitals['daily_std']).round(1)
        hospitals['optimal']    = (hospitals['predicted'] + hospitals['slack']).round(1)
        hospitals['max_5day']   = (hospitals['daily_avg'] * 5).round(1)
        hospitals['optimal']    = hospitals[['optimal','max_5day']].min(axis=1)
        hospitals['min_needed'] = hospitals['predicted'].round(1)

        total_min     = hospitals['min_needed'].sum()
        total_optimal = hospitals['optimal'].sum()

        if supply >= total_optimal:
            hospitals['allocated'] = hospitals['optimal']
            leftover = round(supply - total_optimal, 1)
        elif supply >= total_min:
            hospitals['allocated'] = hospitals['min_needed']
            remaining    = supply - total_min
            extra_needed = hospitals['optimal'] - hospitals['min_needed']
            for level in ['권역', '지역']:
                mask        = hospitals['er_level'] == level
                level_extra = extra_needed[mask].sum()
                if level_extra > 0 and remaining > 0:
                    give  = min(remaining, level_extra)
                    ratio = give / level_extra
                    hospitals.loc[mask, 'allocated'] += (extra_needed[mask] * ratio).round(1)
                    remaining -= give
            leftover = round(remaining, 1)
        else:
            er_mask  = hospitals['er_level'] == '권역'
            gen_mask = hospitals['er_level'] == '지역'
            er_min   = hospitals.loc[er_mask,  'min_needed'].sum()
            gen_min  = hospitals.loc[gen_mask, 'min_needed'].sum()
            if supply >= er_min:
                hospitals.loc[er_mask, 'allocated'] = hospitals.loc[er_mask, 'min_needed']
                remaining = supply - er_min
                if gen_min > 0:
                    ratio = min(remaining / gen_min, 1.0)
                    hospitals.loc[gen_mask, 'allocated'] = (
                        hospitals.loc[gen_mask, 'min_needed'] * ratio).round(1)
            else:
                ratio = supply / er_min
                hospitals.loc[er_mask, 'allocated'] = (
                    hospitals.loc[er_mask, 'min_needed'] * ratio).round(1)
                hospitals.loc[gen_mask, 'allocated'] = 0
            leftover = 0

        hospitals['allocated']       = hospitals['allocated'].round(1)
        hospitals['shortage']        = (hospitals['actual_use'] - hospitals['allocated']).clip(lower=0).round(1)
        hospitals['surplus']         = (hospitals['allocated'] - hospitals['actual_use']).clip(lower=0).round(1)
        hospitals['center_supply']   = supply
        hospitals['center_leftover'] = leftover
        results.append(hospitals)

    return pd.concat(results) if results else pd.DataFrame()
