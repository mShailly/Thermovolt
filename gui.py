"""Tkinter companion: classes, a background thread, shared model and database."""
import tkinter as tk
from tkinter import ttk,messagebox
from threading import Thread
from queue import Queue,Empty
from dataclasses import asdict
from datetime import datetime,timezone
import uuid,json
from thermovolt.core import Conditions,CoolingOptimizer
from thermovolt.storage import initialize,connection,execute
class ThermoVoltGUI:
    def __init__(self,root):
        self.root=root;self.root.title('ThermoVolt AI — Python companion');self.root.geometry('720x610');self.queue=Queue();self.optimizer=CoolingOptimizer();self.result=None;initialize()
        tk.Label(root,text='ThermoVolt AI',font=('Helvetica',25,'bold'),fg='#14213d').pack(pady=15)
        tk.Label(root,text='Educational microchannel cooling simulation').pack()
        self.values={};frame=ttk.Frame(root);frame.pack(pady=15)
        labels={'start':'Starting temperature (°C)','heat':'Heat per cell (W)','inlet':'Coolant inlet (°C)','ambient':'Ambient temperature (°C)','concentration':'Al₂O₃ concentration (%)','target':'Final target (°C)','spreadLimit':'Final spread target (°C)','fixedFlow':'Fixed comparison flow (mL/min)'}
        for i,(key,value) in enumerate(asdict(Conditions()).items()):
            ttk.Label(frame,text=labels[key]).grid(row=i,column=0,padx=12,pady=6,sticky='w');var=tk.StringVar(value=str(value));ttk.Entry(frame,textvariable=var,width=16).grid(row=i,column=1);self.values[key]=var
        self.run_button=ttk.Button(root,text='Run comparison in background thread',command=self.start);self.run_button.pack(pady=8)
        self.output=tk.StringVar(value='Adjust conditions and run a comparison.');ttk.Label(root,textvariable=self.output,justify='left',wraplength=650).pack(pady=12)
        self.save_button=ttk.Button(root,text='Save result to shared database',command=self.save,state='disabled');self.save_button.pack()
        self.root.after(100,self.poll)
    def start(self):
        try:payload={key:float(var.get()) for key,var in self.values.items()};Conditions.from_dict(payload)
        except ValueError as error:messagebox.showerror('Invalid conditions',str(error));return
        self.run_button.configure(state='disabled');self.output.set('Running… GUI remains responsive.')
        def worker():
            try:self.queue.put(('ok',self.optimizer.optimize(payload)))
            except Exception as error:self.queue.put(('error',str(error)))
        Thread(target=worker,daemon=True).start()
    def poll(self):
        try:
            state,value=self.queue.get_nowait();self.run_button.configure(state='normal')
            if state=='error':messagebox.showerror('Simulation failed',value)
            else:
                self.result=value;s=value['optimized'];self.output.set(f"Flow: {s['flow']:.1f} mL/min per channel\nFinal hottest cell: {s['end']['max']:.2f}°C · spread: {s['end']['spread']:.2f}°C\nTargets met: {value['feasible']} · hydraulic pump power: {s['power']:.5f} W");self.save_button.configure(state='normal')
        except Empty:pass
        self.root.after(100,self.poll)
    def save(self):
        try:
            r=self.result;s=r['optimized'];results={'flow':s['flow'],'finalMax':s['end']['max'],'spread':s['end']['spread'],'energyWh':s['energyWh'],'feasible':r['feasible']}
            with connection() as conn:execute(conn,'INSERT INTO experiments VALUES(?,?,?,?,?)',(str(uuid.uuid4()),'Tkinter cooling experiment',json.dumps(r['conditions']),json.dumps(results),datetime.now(timezone.utc).isoformat()))
            messagebox.showinfo('Saved','Refresh Experiments & records in the website to see this run.')
        except Exception as error:messagebox.showerror('Database error',str(error))
if __name__=='__main__':
    root=tk.Tk();ThermoVoltGUI(root);root.mainloop()
