"""Fit both SOC models on known values; evaluate only supplied masked truths."""
import argparse
from pathlib import Path
import numpy as np,pandas as pd
parser=argparse.ArgumentParser();parser.add_argument('missing',type=Path);parser.add_argument('truth',type=Path);args=parser.parse_args()
df=pd.read_csv(args.missing);truth=pd.read_csv(args.truth);missing=df['State of Charge'].isna();train=df.loc[~missing];indices=truth.Row_Index.to_numpy(int)
if len(set(indices))!=len(indices) or set(indices)!=set(np.flatnonzero(missing)):raise ValueError('Truth indices must exactly match missing SOC rows.')
y=train['State of Charge'].to_numpy();actual=truth.Actual_State_of_Charge.to_numpy()
for name,columns in [('Simple',['Battery_Voltage']),('Multiple',['Battery_Voltage','Battery_Current','Battery_Temperature'])]:
 X=np.column_stack([np.ones(len(train)),train[columns].to_numpy()]);w=np.linalg.lstsq(X,y,rcond=None)[0];test=np.column_stack([np.ones(len(indices)),df.loc[indices,columns].to_numpy()]);prediction=test@w;e=prediction-actual
 print(name,'coefficients',w,'MAE',np.mean(abs(e)),'RMSE',np.sqrt(np.mean(e**2)),'R2',1-np.sum(e**2)/np.sum((actual-actual.mean())**2))
