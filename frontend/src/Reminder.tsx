import React,{useEffect,useRef,useState} from 'react';
export default function Reminder({count,critical=false}:{count:number;critical?:boolean}){
 const [enabled,setEnabled]=useState(false),[note,setNote]=useState(''),[ring,setRing]=useState(0);const context=useRef<AudioContext|null>(null),latest=useRef({count,critical}),last=useRef(0);
 latest.current={count,critical};
 function beep(){const c=context.current;if(!c||c.state!=='running')return;for(let i=0;i<3;i++){const o=c.createOscillator(),g=c.createGain(),t=c.currentTime+i*.22;o.connect(g);g.connect(c.destination);o.frequency.value=latest.current.critical?880:660;g.gain.setValueAtTime(.065,t);g.gain.exponentialRampToValueAtTime(.001,t+.15);o.start(t);o.stop(t+.16)}last.current=Date.now();setRing(n=>n+1)}
 async function toggle(){if(enabled){setEnabled(false);setNote('');return}try{const C=window.AudioContext||(window as any).webkitAudioContext;context.current??=new C();await context.current!.resume();setEnabled(true);setNote('Reminds every minute while this page is open.');if(count)beep()}catch{setNote('Sound could not start. Check browser audio permissions.')}}
 useEffect(()=>{if(!enabled)return;const tick=()=>{if(latest.current.count&&Date.now()-last.current>=60000)beep()};const timer=setInterval(tick,1000);document.addEventListener('visibilitychange',tick);return()=>{clearInterval(timer);document.removeEventListener('visibilitychange',tick)}},[enabled]);
 useEffect(()=>{if(enabled&&count>0&&last.current===0)beep()},[count,enabled]);
 useEffect(()=>()=>{void context.current?.close()},[]);
 return <div className="reminder"><button className="secondary-button" onClick={toggle}>{enabled?'Mute reminders':'Enable sound'}</button><span role="status">{enabled&&count?(count+' active alerts · reminder every minute'):enabled?'Sound on · no active alerts':'Sound off'}{ring>0&&count?' · Please review alerts':''}</span>{note&&<small>{note}</small>}</div>
}
