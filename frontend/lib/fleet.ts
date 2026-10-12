import {defaults,hydraulic,optimize,predict,type Conditions} from './thermal';

export type DriveMode='auto'|'normal'|'hard-acceleration'|'high-speed'|'hot-weather'|'high-load'|'cell-hotspot'|'coolant-leak';
export type VehicleProfile={id:string;name:string;model:string;className:string;capacity:number;nominalVoltage:number;soh:number;baseSpeed:number;maxSpeed:number;baseTemp:number;cooling:number;accent:string};
export type Contributor={code:string;label:string;level:'moderate'|'high';evidence:string;detail:string};
export type FleetAlert={code:string;severity:'warning'|'critical';title:string;message:string;action:string};
export type FleetFrame={time:string;elapsed:number;vehicleId:string;driveMode:DriveMode;condition:string;temperature:number;averageTemperature:number;cells:number[];soc:number;soh:number;voltage:number;current:number;ambient:number;motorTemp:number;motorTorque:number;rpm:number;speed:number;acceleration:number;distance:number;cycles:number;idle:number;power:number;regen:number;flow:number;inlet:number;heat:number;pressure:number;recommendation:number;forecast:number|null;spread:number;feasible:boolean;pump:number;contributors:Contributor[];alerts:FleetAlert[]};

export const vehicles:VehicleProfile[]=[
 {id:'TV-URBAN-01',name:'Urban One',model:'Eon City',className:'Compact city EV',capacity:45,nominalVoltage:330,soh:96,baseSpeed:42,maxSpeed:135,baseTemp:31,cooling:.94,accent:'#0b88a1'},
 {id:'TV-FAMILY-02',name:'Family Prime',model:'Aster X7',className:'Family SUV',capacity:72,nominalVoltage:390,soh:93,baseSpeed:58,maxSpeed:185,baseTemp:33,cooling:1.08,accent:'#3768b1'},
 {id:'TV-SPORT-03',name:'Volt GT',model:'Veloce S',className:'Electric sports coupe',capacity:88,nominalVoltage:720,soh:91,baseSpeed:76,maxSpeed:255,baseTemp:35,cooling:1.28,accent:'#7554c7'},
 {id:'TV-TRACK-04',name:'Apex R',model:'Ion R9',className:'Track performance EV',capacity:92,nominalVoltage:800,soh:89,baseSpeed:94,maxSpeed:305,baseTemp:37,cooling:1.48,accent:'#d0643b'},
 {id:'TV-FLEET-05',name:'Metro Van',model:'Carry E5',className:'Electric delivery van',capacity:105,nominalVoltage:610,soh:86,baseSpeed:48,maxSpeed:150,baseTemp:34,cooling:1.14,accent:'#358268'}
];
export const vehicleById=(id:string)=>vehicles.find(v=>v.id===id.toUpperCase());
const clamp=(n:number,a:number,b:number)=>Math.min(b,Math.max(a,n));
export const automaticConditions:Record<string,DriveMode>={'TV-URBAN-01':'normal','TV-FAMILY-02':'hot-weather','TV-SPORT-03':'high-load','TV-TRACK-04':'cell-hotspot','TV-FLEET-05':'coolant-leak'};
const labels:Record<DriveMode,string>={auto:'Adaptive route','normal':'Steady driving','hard-acceleration':'Rapid acceleration','high-speed':'Sustained high speed','hot-weather':'Hot ambient conditions','high-load':'High battery load','cell-hotspot':'Cell hotspot','coolant-leak':'Coolant-flow loss'};

export function nextFleetFrame(profile:VehicleProfile,previous: FleetFrame|null,requested:DriveMode='auto'):FleetFrame{
 const elapsed=(previous?.elapsed??-20)+20;
 const mode=requested==='auto'?automaticConditions[profile.id]:requested;
 const phase=elapsed/25;let speed=profile.baseSpeed+Math.sin(phase)*7,acceleration=.4+Math.sin(phase*.8)*.45,ambient=29,current=-(58+profile.capacity*.32),inlet=24;
 if(mode==='hard-acceleration'){acceleration=4.1;speed=clamp((previous?.speed??profile.baseSpeed)+18,0,profile.maxSpeed*.82);current=-(170+profile.capacity*.7);}
 if(mode==='high-speed'){speed=profile.maxSpeed*.84;acceleration=.8;current=-(155+profile.capacity*.55);}
 if(mode==='hot-weather'){ambient=43;inlet=33;speed=profile.baseSpeed*1.12;current=-(95+profile.capacity*.4);}
 if(mode==='high-load'){speed=profile.baseSpeed*.9;acceleration=2.1;current=-(205+profile.capacity*.65);}
 if(mode==='cell-hotspot'){speed=profile.baseSpeed;current=-(105+profile.capacity*.4);}
 if(mode==='coolant-leak'){speed=profile.baseSpeed*.95;current=-(115+profile.capacity*.4);}
 const highSpeed=Math.max(0,speed-115),highAmbient=Math.max(0,ambient-34);
 const heat=clamp(3.1+Math.abs(current)/43+Math.max(0,acceleration-1)*.72+highSpeed*.024+highAmbient*.11,2,14);
 const initial=mode==='normal'?profile.baseTemp:mode==='hot-weather'?44:mode==='high-load'?44:mode==='cell-hotspot'?40:39;
 const prior=previous?.cells?.length===10?previous.cells:Array.from({length:10},(_,i)=>initial+(i-4.5)*.07+(mode==='cell-hotspot'&&i===6?8:0));
 const average=prior.reduce((a,b)=>a+b,0)/prior.length;
 const conditions:Conditions={...defaults,start:clamp(average,25,55),heat,inlet,ambient};
 const result=optimize(conditions),recommendation=result.optimized.flow;
 const pump=recommendation*profile.cooling,flow=mode==='coolant-leak'?pump*.28:pump;
 const cells=prior.map((temperature,i)=>{const offset=(i/9*2-1),g=flow<1?.015:(.05+.48*(Math.max(flow,1)/20)**.55*1.04)*(1+.06*offset)*profile.cooling;const eq=(heat*(1+.12*offset)+g*inlet+.04*ambient)/(g+.04);let next=eq+(temperature-eq)*Math.exp(-(g+.04)*20/70);if(mode==='cell-hotspot'&&i===6)next+=1.15;return next;});
 const temperature=Math.max(...cells),averageTemperature=cells.reduce((a,b)=>a+b,0)/cells.length,spread=temperature-Math.min(...cells);
 const prediction=flow>=10&&flow<=60&&temperature>=25&&temperature<=55?predict({...conditions,start:temperature},flow).temperature:null;
 const soc=clamp((previous?.soc??(76-profile.capacity%9))-Math.abs(profile.nominalVoltage*current)*20/3_600_000/profile.capacity*100,4,100);
 const power=Math.abs(profile.nominalVoltage*current),contributors:Contributor[]=[];
 const add=(code:string,label:string,level:'moderate'|'high',evidence:string,detail:string)=>contributors.push({code,label,level,evidence,detail});
 if(acceleration>2.5)add('acceleration','Rapid acceleration',acceleration>3.6?'high':'moderate',`${acceleration.toFixed(1)} m/s² acceleration`,'Higher torque demand is increasing battery current and heat generation.');
 if(speed>120)add('speed','Sustained high speed',speed>profile.maxSpeed*.8?'high':'moderate',`${speed.toFixed(0)} km/h vehicle speed`,'Sustained propulsion demand is adding thermal load.');
 if(Math.abs(current)>190)add('load','High battery load',Math.abs(current)>235?'high':'moderate',`${Math.abs(current).toFixed(0)} A discharge current`,'High current is the strongest present electrical heating contributor.');
 if(ambient>38)add('weather','Hot weather',ambient>42?'high':'moderate',`${ambient.toFixed(0)}°C ambient temperature`,'Hot surroundings reduce the temperature difference available for heat rejection.');
 if(flow<recommendation*.6)add('coolant','Reduced coolant flow','high',`${flow.toFixed(1)} of ${recommendation.toFixed(1)} mL/min requested`,'Cooling delivery is below the present thermal recommendation.');
 if(spread>=4||mode==='cell-hotspot')add('hotspot','Cell hotspot',spread>=5?'high':'moderate',`${spread.toFixed(1)}°C cell spread`,'One area of the pack is warming faster than the rest.');
 const alerts:FleetAlert[]=[];
 if(mode==='high-load'&&Math.abs(current)>235)alerts.push({code:'load',severity:'warning',title:'Sustained high discharge load',message:`Battery discharge is ${Math.abs(current).toFixed(0)} A. Elevated electrical demand is increasing heat generation.`,action:'Reduce sustained load and monitor the cooling response.'});
 if(mode==='hot-weather'&&ambient>=42)alerts.push({code:'ambient',severity:'warning',title:'High ambient thermal stress',message:`Ambient temperature is ${ambient.toFixed(0)}°C, reducing available heat rejection.`,action:'Monitor pack temperature and keep the cooling circuit operating.'});
 const likely=contributors.slice(0,3).map(c=>c.label).join(', ');
 if(flow<recommendation*.6)alerts.push({code:'coolant',severity:'critical',title:'Cooling flow below demand',message:`Reported flow is ${flow.toFixed(1)} mL/min while ${recommendation.toFixed(1)} mL/min is requested.`,action:'Inspect the coolant circuit and pump response.'});
 if(temperature>=50)alerts.push({code:'temperature',severity:'critical',title:'Battery temperature critical',message:`Hottest cell is ${temperature.toFixed(1)}°C.`,action:'Reduce load and follow the vehicle thermal-protection procedure.'});
 else if(temperature>45)alerts.push({code:'temperature',severity:'warning',title:'Battery temperature above target',message:`Hottest cell is ${temperature.toFixed(1)}°C.${likely?` Likely contributors: ${likely}.`:''}`,action:'Review the listed heating contributors and cooling response.'});
 else if(temperature>=43&&contributors.length)alerts.push({code:'margin',severity:'warning',title:'Thermal margin reducing',message:`Hottest cell is ${temperature.toFixed(1)}°C and trending near the 45°C target. Likely contributors: ${likely}.`,action:'Reduce the strongest present contributor and confirm temperature begins to stabilise.'});
 else if(prediction!==null&&prediction>45)alerts.push({code:'forecast',severity:'warning',title:'Temperature approaching limit',message:`Projected temperature is ${prediction.toFixed(1)}°C.`,action:'Reduce the strongest present load factor and monitor the next readings.'});
 if(spread>=5)alerts.push({code:'spread',severity:'warning',title:'Uneven cell temperatures',message:`Cell spread has reached ${spread.toFixed(1)}°C.`,action:'Inspect the hottest cell area and coolant distribution.'});
 return{time:new Date().toISOString(),elapsed,vehicleId:profile.id,driveMode:mode,condition:labels[mode],temperature,averageTemperature,cells,soc,soh:profile.soh,voltage:profile.nominalVoltage,current,ambient,motorTemp:45+Math.abs(current)*.18,motorTorque:Math.abs(current)*.72,rpm:1800+speed*42,speed,acceleration,distance:(previous?.distance??12540)+speed*20/3600,cycles:190+(100-profile.soh)*9,idle:speed<2?(previous?.idle??0)+20:0,power,regen:mode==='normal'?68:56,flow,inlet,heat,pressure:hydraulic(conditions,flow).pressure,recommendation,forecast:prediction,spread,feasible:result.feasible,pump,contributors,alerts};
}
