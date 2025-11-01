import{r as e}from"./table.js";function o(t,r){const n=e.useRef(()=>{});e.useEffect(()=>{n.current=t},[t]),e.useEffect(()=>{if(r===null)return;const s=window.setInterval(()=>{n.current()},r);return()=>window.clearInterval(s)},[r])}export{o as u};
//# sourceMappingURL=useInterval.js.map
