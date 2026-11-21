import QtQuick
import "SectionData.js" as SD
import "ActivityPresentation.js" as Presentation

QtObject {
    id: shelf
    required property var host
    readonly property var games: [
        ["endfield","终末地"],["starrail","崩坏：星穹铁道"],["genshin","原神"],["wutheringwaves","鸣潮"],
        ["arknights","明日方舟"],["zenless","绝区零"],["nte","异环"],["reverse1999","重返未来：1999"],
        ["bluearchive","碧蓝档案"],["stellasora","星塔旅人"],["infinitynikki","无限暖暖"]]
    property string server: "cn"
    property var cache: ({})
    property var requests: ({})
    property var pending: ({})
    property int serial: 0
    property Connections feeds: Connections {
        target:activityFeed
        function onReceived(game,version,json) { shelf.accept(game,version,JSON.parse(json)) }
    }
    function records() { return games.map(pair=>card(pair[0],pair[1])) }
    function publish() {
        if(host.d?.key==="activity" && host.opened && host.api)host.setLive("activity",records())
    }
    function card(game,name) {
        const state=cache[game] || {},data=state.data
        const ops={"刷新":{perform:()=>load(game,true)}},actions=["刷新"]
        let blocks=[]
        if (!data) blocks.push(SD.note(state.error || (!host.api?"等待后端连接":pending[game]?"正在读取活动源…":"等待读取活动源"),true))
        else blocks.push({
            t:"calendar",game:game,name:name,data:data,
            completed:host.api && !state.markReading?state.completed || null:null,pendingKey:state.pendingKey || "",
            error:state.error?(state.error+" · 显示上次成功读取的数据"):"",
            markError:state.markError || "",toggle:(row,done)=>toggle(game,row,done)
        })
        if(game==="bluearchive") {
            const choose=SD.sel(["国服","日服","国际服"],["cn","jp","global"].indexOf(server))
            blocks.unshift(SD.kv("服务器",[["服务器",choose]]))
            ops["切换服务器"]={perform:()=>{
                server=["cn","jp","global"][choose.v]
                delete cache[game]
                requests[game]=++serial;pending[game]=false
                load(game,true)
            }}
            actions.unshift("切换服务器")
        }
        return {name:name,en:"GAME CALENDAR",uid:game,live:true,scrollBody:true,
            blocks:blocks,ops:ops,actions:actions}
    }
    function toggle(game,row,done) {
        const state=cache[game]
        if(!host.api || !state?.completed || state.pendingKey)return
        const version=requests[game],key=Presentation.key(row)
        state.pendingKey=key
        publish()
        host.call("/api/info/activity/completions",{
            game:game,server:game==="bluearchive"?server:"cn",name:row.name,
            startTime:new Date(Presentation.time(row.startTime)).toISOString(),
            endTime:new Date(Presentation.time(row.endTime)).toISOString(),completed:done
        },r=>{
            if(requests[game]!==version)return
            state.pendingKey=""
            if(r.code!==200){host.toastText(r.message || "完成状态未保存");publish();return}
            state.completed=state.completed.filter(value=>value!==key)
            if(done)state.completed.push(key)
            publish()
        })
    }
    function load(game,force) {
        if(!host.api || !game || cache[game]?.pendingKey)return
        if(pending[game] || (!force && (cache[game]?.updated || 0)>Date.now()-300000))return
        const version=++serial
        requests[game]=version;pending[game]=true
        publish()
        if(game==="arknights") {
            host.api.get("/api/info/arknights/activity",text=>{
                let r
                try{r=JSON.parse(text)}catch(e){r={code:0}}
                if(r.data)r.data.source="PRTS / SRA"
                accept(game,version,r)
                if(r.code===200)host.call("/api/info/get/overview",{},overview=>{
                    if(requests[game]!==version)return
                    const data=cache[game]?.data
                    if(!data)return
                    data.resources=(overview.data?.Stage?.Resource || []).map(item=>({
                        name:item.DropName,kind:item.Display,description:item.Activity?.Tip || "",
                        cover:item.Drop?"http://127.0.0.1:"+host.api.port+"/api/res/materials/"+encodeURIComponent(item.Drop)+".png":""
                    }))
                    data.resourceError=overview.code===200?"":overview.message || "资源关卡读取失败"
                    publish()
                })
            })
        } else if(game==="stellasora")host.call("/api/info/stella/activity",{},r=>{
            if(r.data)r.data.source="星塔旅人官方公告"
            accept(game,version,r)
        })
        else if(game==="bluearchive") {
            const list=[],activeServer=server
            function batch(n) {
                host.call("/api/info/bluearchive/activity",{
                    line_type:activeServer==="global"?"Globle":activeServer.toUpperCase(),page:n,page_size:100
                },r=>{
                    if(requests[game]!==version)return
                    const rows=r.data?.data
                    if(r.code!==200 || !Array.isArray(rows)){accept(game,version,{code:500,message:r.message || "GameKee 无数据"});return}
                    rows.forEach(x=>{
                        if(!x.title || !x.begin_at || x.end_at<=x.begin_at)return
                        const picture=(x.picture || "").startsWith("//")?"https:"+x.picture:x.picture || ""
                        list.push({name:x.title,description:x.description || "",kind:x.activity_kind_name || "",
                            startTime:new Date(x.begin_at*1000).toISOString(),endTime:new Date(x.end_at*1000).toISOString(),
                            cover:picture?"http://127.0.0.1:"+host.api.port+"/api/info/bluearchive/image?url="+encodeURIComponent(picture):""})
                    })
                    if(n===1 && rows.length===100)batch(2)
                    else {
                        const unique={}
                        list.forEach(row=>{
                            if(!unique[row.name] || Presentation.time(unique[row.name].endTime)<Presentation.time(row.endTime))unique[row.name]=row
                        })
                        accept(game,version,{code:200,data:{source:"GameKee",activities:Object.values(unique)}})
                    }
                })
            }
            batch(1)
        } else activityFeed.load(game,version)
    }
    function accept(game,version,r) {
        if(requests[game]!==version)return
        pending[game]=!!r.partial
        const state=cache[game] || {}
        cache[game]=state
        if(r.code!==200 || !Array.isArray(r.data?.activities)){
            state.error=r.message || "活动源不可用";publish();return
        }
        const old=state.data
        // 两个来源独立失败时保留该来源最近一次成功结果。
        if(game==="endfield" && old) {
            if(r.data.poolError && old.pools?.length)r.data.pools=old.pools
            if(r.data.activityError && old.source?.startsWith("SRA")){
                for(const key of ["activities","version","versionName","cover","startTime","endTime"])r.data[key]=old[key]
            }
        }
        state.data=r.data;state.error="";state.updated=Date.now()
        const readMarks=host.api && state.markReading!==version && state.markRead!==version
        if(readMarks)state.markReading=version
        publish()
        if(!readMarks)return
        host.api.get("/api/info/activity/completions?game="+game+"&server="+(game==="bluearchive"?server:"cn"),text=>{
            if(requests[game]!==version)return
            let reply
            try{reply=JSON.parse(text)}catch(e){}
            state.markReading=0;state.markRead=version
            state.completed=reply?.code===200?reply.data.map(Presentation.key):null
            state.markError=state.completed?"":"完成状态读取失败，请刷新"
            publish()
        })
    }
}
