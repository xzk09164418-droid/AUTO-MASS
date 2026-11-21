.pragma library

function time(value) {
    if (!value) return 0
    const text = String(value)
    const zoned = /^\d{4}-\d\d-\d\d[T ]\d\d:\d\d(:\d\d)?$/.test(text)
        ? text.replace(" ", "T") + "+08:00" : text
    return Date.parse(zoned) || 0
}
function key(row) { return JSON.stringify([row.name, time(row.startTime), time(row.endTime)]) }
function current(row, now) { return time(row.startTime) <= now && time(row.endTime) > now }
function byEnd(a, b) { return time(a.endTime) - time(b.endTime) }
function longRunning(row) { return time(row.endTime) - time(row.startTime) > 60 * 86400000 }
function permanent(row) {
    const name = row.name.trim().toLowerCase()
    return ["虚构叙事", "混沌回忆", "末日幻影", "pure fiction", "memory of chaos", "apocalyptic shadow"]
        .some(prefix => name.startsWith(prefix))
}
function build(game, name, data, now) {
    const valid = (data.activities || []).filter(row => row.name && time(row.endTime) > time(row.startTime))
    let entries, extra = []
    if (game === "endfield") {
        entries = valid.filter(row => time(row.endTime) > now).sort((a,b) =>
            Number(time(a.startTime) > now) - Number(time(b.startTime) > now) || byEnd(a,b))
        extra = [{title:"寻访卡池", kind:"pools",
            rows:(data.pools || []).filter(row => current(row,now)).sort(byEnd),
            error:data.poolError || "", loading:!!data.poolsLoading}]
    } else if (game === "arknights") {
        entries = valid.filter(row => time(row.endTime) > now).sort((a,b) =>
            Number(longRunning(a)) - Number(longRunning(b)) || time(a.startTime)-time(b.startTime)).slice(0,8).map(row=>Object.assign({},row,{daysOnly:longRunning(row)}))
    } else if (game === "bluearchive") {
        entries=valid.filter(row=>current(row,now)).sort(byEnd).concat(
            valid.filter(row=>time(row.startTime)>now).sort((a,b)=>time(a.startTime)-time(b.startTime))).slice(0,6)
    } else {
        entries = valid.filter(row => current(row,now)).sort(byEnd)
        if (game === "starrail") {
            const fixed = entries.filter(permanent)
            entries = entries.filter(row => !permanent(row))
            if (fixed.length) extra.push({title:"常驻玩法",kind:"activities",rows:fixed})
        }
        if(game==="stellasora"){
            const fixed=valid.filter(row=>row.kind==="常驻活动" && time(row.endTime)>now).sort(byEnd)
            entries=entries.filter(row=>row.kind!=="常驻活动")
            if(fixed.length)extra.push({title:"常驻活动",kind:"activities",rows:fixed})
        }
    }
    if(game==="arknights" && (data.resources?.length || data.resourceError)){
        extra.push({title:"今日资源",kind:"resources",rows:data.resources || [],error:data.resourceError || ""})
    }
    let primary = valid.filter(row => current(row,now)).sort(byEnd)[0]
        || valid.find(row => time(row.endTime)>now)
    if(game==="stellasora")primary=valid.find(row=>(row.kind || "").includes("版本活动") && current(row,now))
        || valid.find(row=>(row.kind || "").includes("版本活动") && time(row.startTime)>now)
    if(game==="arknights"){
        const pick=rows=>rows.find(row=>current(row,now)) || rows.find(row=>time(row.startTime)>now)
        primary=pick(valid.filter(row=>["支线故事","复刻活动","联动活动"].some(k=>(row.kind || "").includes(k))))
            || pick(valid.filter(row=>(row.kind || "").includes("其他活动")))
    }
    const validVersion = data.versionName && data.endTime
        && (game !== "endfield" || time(data.endTime) > now)
    const row = validVersion ? {name:data.versionName,startTime:data.startTime,endTime:data.endTime} : primary
    return {
        name:name, game:game, source:data.source || "", error:data.activityError || "",
        banner:{
            title:row?.name || name, version:validVersion ? data.version : "",
            startTime:row?.startTime || "", endTime:row?.endTime || "",
            cover:game==="endfield" ? (validVersion?data.cover || "":"") : ["arknights","stellasora"].includes(game) ? primary?.cover || "" : data.cover || valid.find(r=>r.cover)?.cover || ""
        },
        sections:extra.concat([{title:"活动日程",kind:"activities",rows:entries}])
    }
}
function duration(row, now) {
    const upcoming = time(row.startTime)>now
    const target = upcoming ? time(row.startTime) : time(row.endTime)
    if (!target) return ""
    if (row.daysOnly) return (upcoming?"距开始 ":"剩余 ")+Math.max(0,Math.ceil((target-now)/86400000))+" 天"
    const hours = Math.max(0,Math.ceil((target-now)/3600000))
    if (target<=now && !upcoming) return "已结束"
    return (upcoming?"距开始 ":"剩余 ") + Math.floor(hours/24)+" 天 "+hours%24+" 时"
}
function boundary(row, now) {
    const upcoming = time(row.startTime)>now
    const value = time(upcoming?row.startTime:row.endTime)
    if(!value)return ""
    // 公开源日程统一按 UTC+8 展示，避免宿主时区改变活动日期。
    const date=new Date(value+8*3600000)
    const pad=n=>String(n).padStart(2,"0")
    return (upcoming?"开始 ":"结束 ")+date.getUTCFullYear()+"/"+pad(date.getUTCMonth()+1)+"/"+
        pad(date.getUTCDate())+" "+pad(date.getUTCHours())+":"+pad(date.getUTCMinutes())+" UTC+8"
}

