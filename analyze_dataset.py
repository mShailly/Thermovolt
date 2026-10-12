"""Full-dataset FDS analysis and C interval queries, with original data preserved."""
import argparse,json
from pathlib import Path
import numpy as np,pandas as pd
from thermovolt.segment import CSegmentTree
parser=argparse.ArgumentParser();parser.add_argument('dataset',type=Path);parser.add_argument('--start',type=int,default=0);parser.add_argument('--end',type=int,default=99);args=parser.parse_args()
df=pd.read_csv(args.dataset);print('Dataset shape:',df.shape);print('Missing values:',df.isna().sum().to_dict())
for col in df.select_dtypes('number'):
 s=df[col].dropna();print(col,{'mean':s.mean(),'median':s.median(),'population_sd':s.std(ddof=0),'q1':s.quantile(.25),'q3':s.quantile(.75)})
values=df.Battery_Temperature.to_numpy(float);tree=CSegmentTree(values);print('C interval query:',tree.query(args.start,args.end));tree.close()
print('Temperature correlations:',df.select_dtypes('number').corr().Battery_Temperature.to_dict())
# Scaling and equal-width discretization without overwriting the source CSV.
s=df.Battery_Temperature;scaled=(s-s.min())/(s.max()-s.min());bins=pd.cut(s,bins=3,labels=['low','medium','high']);print('Normalized temperature sample:',scaled.head().tolist());print('Bin counts:',bins.value_counts().to_dict())
