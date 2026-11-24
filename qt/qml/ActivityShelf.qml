import QtQuick
import "SectionData.js" as SD
import "ActivityPresentation.js" as Presentation

QtObject {
    id: shelf
    required property var host
    // 仅依据用户登记的托管名称匹配；英文缩写须有词边界，避免 ww 匹配 www。
    readonly property var catalog: [
        ["endfield","终末地",/终末地|(?:^|[^a-z0-9])(?:maaend|endfield)(?=$|[^a-z0-9])/],
        ["starrail","崩坏：星穹铁道",/崩铁|星铁|星穹铁道|(?:^|[^a-z0-9])(?:hsr|src|star[ _-]*rail|march7th(?:assistant)?)(?=$|[^a-z0-9])/],
        ["genshin","原神",/原神|(?:^|[^a-z0-9])(?:genshin(?:[ _-]*impact)?|bettergi|bgi|ys)(?=$|[^a-z0-9])/],
        ["wutheringwaves","鸣潮",/鸣潮|鳴潮|(?:^|[^a-z0-9])(?:ww|wuwa|wuthering[ _-]*waves)(?=$|[^a-z0-9])/],
        ["arknights","明日方舟",/明日方舟(?![ ：:_-]*终末地)|(?:^|[^a-z0-9])(?:maa|ak|arknights(?![ :_-]*endfield))(?=$|[^a-z0-9])/],
        ["zenless","绝区零",/绝区零|絕區零|(?:^|[^a-z0-9])(?:zzz|zenless[ _-]*zone[ _-]*zero|zzzscript)(?=$|[^a-z0-9])/],
        ["nte","异环",/异环|異環|(?:^|[^a-z0-9])(?:nte|neverness[ _-]*to[ _-]*everness)(?=$|[^a-z0-9])/],
        ["reverse1999","重返未来：1999",/重返未来|重返未來|(?:^|[^a-z0-9])(?:m9a|1999|reverse[ :_-]*1999)(?=$|[^a-z0-9])/],
        ["bluearchive","蔚蓝档案",/蔚蓝档案|碧蓝档案|蔚藍檔案|(?:^|[^a-z0-9])(?:baah|ba|blue[ _-]*archive)(?=$|[^a-z0-9])/],
        ["stellasora","星塔旅人",/星塔旅人|(?:^|[^a-z0-9])(?:stella[ _-]*sora|mss|xtlr)(?=$|[^a-z0-9])/],
        ["infinitynikki","无限暖暖",/无限暖暖|無限暖暖|(?:^|[^a-z0-9])(?:infinity[ _-]*nikki|whimbox)(?=$|[^a-z0-9])/]]
    readonly property var portraitGames: ["endfield","starrail","genshin","wutheringwaves","arknights",
                                          "zenless","nte","reverse1999","bluearchive"]
    property var games: []
    function matched(options) {
        const names = options.filter(o => o.value && o.value !== "-")
            .map(o => String(o.label || "").replace(/^[^-]+? - /, "").normalize("NFKC").toLowerCase())
        return catalog.filter(entry => names.some(name => entry[2].test(name)))
    }
    function refresh(generation) {
        host.call("/api/info/combox/script", {}, result => Qt.callLater(() => {
            if (!host.opened || host.d?.key !== "activity" || host.sectionGeneration !== generation) return
            if (result.code !== 200 || !Array.isArray(result.data)) {
                games = []
                const next = Object.assign({}, host.live)
                delete next.activity
                host.live = next
                host.fail(result)
                return
            }
            const oldGame = host.item?.uid
            games = matched(result.data)
            const cards = records()
            if (!cards.length) cards.push({name:"游戏活动", en:"GAME CALENDAR", live:true,
                blocks:[SD.note("没有匹配到已支持游戏的托管名称。",true)], actions:[]})
            host.setLive("activity", cards)
            const previous = games.findIndex(g => g[0] === oldGame)
            if (previous >= 0 && previous !== host.target) host.select(previous)
            load(games[host.target]?.[0], false)
        }))
    }
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
    function publish(game) {
        if (host.d?.key !== "activity" || !host.opened || !host.api || !host.live.activity) return
        if (!updates.includes(game)) updates.push(game)
        Qt.callLater(flushUpdates)
    }
    property var updates: []
    function flushUpdates() {
        const dirty = updates
        updates = []
        if (host.d?.key !== "activity" || !host.opened || !host.api || !host.live.activity) return
        const items = host.live.activity
        if (items.some(item => dirty.includes(item.uid)))
            host.setLive("activity",items.map(item => dirty.includes(item.uid) ? card(item.uid,item.name) : item))
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
        const runtimeKey = "activity:" + game + (game === "bluearchive" ? ":" + server : "")
        return {name:name,en:"GAME CALENDAR",uid:game,runtimeKey:runtimeKey,live:true,scrollBody:true,
            artwork:portraitGames.includes(game) ? Qt.resolvedUrl("../assets/activity/"+game+".png").toString() : "",
            blocks:blocks,ops:ops,actions:actions}
    }
    function toggle(game,row,done) {
        const state=cache[game]
        if(!host.api || !state?.completed || state.pendingKey)return
        const version=requests[game],key=Presentation.key(row)
        state.pendingKey=key
        publish(game)
        host.call("/api/info/activity/completions",{
            game:game,server:game==="bluearchive"?server:"cn",name:row.name,
            startTime:new Date(Presentation.time(row.startTime)).toISOString(),
            endTime:new Date(Presentation.time(row.endTime)).toISOString(),completed:done
        },r=>{
            if(requests[game]!==version)return
            state.pendingKey=""
            if(r.code!==200){host.toastText(r.message || "完成状态未保存");publish(game);return}
            state.completed=state.completed.filter(value=>value!==key)
            if(done)state.completed.push(key)
            publish(game)
        })
    }
    function load(game,force) {
        if(!host.api || !games.some(g=>g[0]===game) || cache[game]?.pendingKey)return
        if(pending[game] || (!force && (cache[game]?.updated || 0)>Date.now()-300000))return
        const version=++serial
        requests[game]=version;pending[game]=true
        publish(game)
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
                    publish(game)
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
            state.error=r.message || "活动源不可用";publish(game);return
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
        publish(game)
        if(!readMarks)return
        host.api.get("/api/info/activity/completions?game="+game+"&server="+(game==="bluearchive"?server:"cn"),text=>{
            if(requests[game]!==version)return
            let reply
            try{reply=JSON.parse(text)}catch(e){}
            state.markReading=0;state.markRead=version
            state.completed=reply?.code===200?reply.data.map(Presentation.key):null
            state.markError=state.completed?"":"完成状态读取失败，请刷新"
            publish(game)
        })
    }
}
