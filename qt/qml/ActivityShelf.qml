import QtQuick
import "SectionData.js" as SD

QtObject {
    id: shelf
    required property var host
    readonly property var games: [["endfield", "终末地"], ["starrail", "崩坏：星穹铁道"], ["genshin", "原神"], ["wutheringwaves",
                                                                                                    "鸣潮"], ["arknights",
                                                                                                            "明日方舟"], ["zenless",
                                                                                                                      "绝区零"], ["nte",
                                                                                                                               "异环"], ["reverse1999",
                                                                                                                                       "重返未来：1999"],
        ["bluearchive", "碧蓝档案"], ["stellasora", "星塔旅人"], ["infinitynikki", "无限暖暖"]]
    property string server: "cn"
    property var cache: ({})
    property var requests: ({})
    property var pending: ({})
    property int serial: 0
    property Connections feeds: Connections {
        target: activityFeed
        function onReceived(key, version, json) {
            shelf.accept(key, version, JSON.parse(json));
        }
    }
    function records() {
        return games.map(pair => card(pair[0], pair[1]));
    }
    function publish() {
        if (host.d?.key === "activity" && host.opened && host.api)
            host.setLive("activity", records());
    }
    function stamp(value) {
        if (!value)
            return NaN;
        const text = String(value);
        return Date.parse(/^\d{4}-\d\d-\d\d[T ]\d\d:\d\d(:\d\d)?$/.test(text) ? text.replace(" ", "T") + "+08:00" :
                                                                                text);
    }
    function keyOf(row) {
        return JSON.stringify([row.name, stamp(row.startTime), stamp(row.endTime)]);
    }
    function card(game, name) {
        const state = cache[game] || {}, data = state.data, now = Date.now();
        const ops = {
            "刷新": {
                perform: () => load(game, true)
            }
        };
        const actions = ["刷新"];
        let blocks = [];
        if (!data)
            blocks.push(SD.note(state.error || (!host.api ? "等待后端连接" : pending[game] ? "正在读取活动源…" : "等待读取活动源"),
                                true));
        else {
            function recent(list) {
                return (list || []).filter(r => r.name && stamp(r.endTime) > now - 14 * 86400000 && stamp(
                                               r.startTime) < stamp(r.endTime)).sort((a, b) => stamp(
                                                                                         a.startTime) - stamp(
                                                                                         b.startTime));
            }
            const rows = recent(data.activities), pools = recent(data.pools);
            const current = rows.find(r => stamp(r.startTime) <= now && stamp(r.endTime) > now) || rows.find(r
                                                                                                             => stamp(r.startTime)
                                                                                                             > now) || rows[rows.length
                                                                                                                            - 1];
            const banner = SD.banner({
                                         v: data.version || data.source,
                                         title: current?.name || name,
                                         left: current ? Math.max(0, Math.ceil((stamp(current.endTime) - now)
                                                                               / 86400000)) + " 天" : "—",
                                         c: ["#17292a", "#39483c", "#6f7757"]
                                     });
            banner.cover = current?.cover || data.cover || "";
            banner.slides = rows.filter(row => stamp(row.endTime) > now).map(row => ({
                                                                                         title: row.name,
                                                                                         cover: row.cover
                                                                                                || data.cover
                                                                                                || "",
                                                                                         left: Math.max(0,
                                                                                                        Math.ceil(
                                                                                                            (stamp(row.endTime)
                                                                                                             - now) / 86400000))
                                                                                               + " 天"
                                                                                     }));
            blocks.push(banner);
            if (state.error)
                blocks.push(SD.note(state.error + " · 正在显示上次读取结果", true));
            const day = s => Qt.formatDateTime(new Date(stamp(s)), "MM/dd HH:mm");
            function schedule(list, title, mark) {
                const entries = list.map(r => {
                                             const cells = [r.name, day(r.startTime), day(r.endTime)];
                                             if (mark) {
                                                 const done = state.completed?.includes(keyOf(r));
                                                 const action = SD.mini([done ? "已完成" : "标记"]);
                                                 action.ops = [
                                                     {
                                                         off: !host.api || !state.completed || stamp(r.endTime) <= now,
                                                         perform: () => toggle(game, r, !done)
                                                     }
                                                 ];
                                                 cells.push(action);
                                             }
                                             return cells;
                                         });
                const table = SD.table(title, mark ? ["活动", "开始", "结束", "完成"] : ["卡池", "开始", "结束"], entries,
                                       mark ? [2.3, 1.1, 1.1, 0.8] : [2, 1, 1]);
                table.pageRows = 4;
                return entries.length ? table : SD.note(title + " · 暂无数据", true);
            }
            blocks.push(schedule(rows, "活动日程", true));
            if (game === "endfield")
                blocks.push(schedule(pools, "寻访卡池", false));
            blocks.push(SD.note("数据来源 · " + data.source + (state.markError ? "　" + state.markError : ""),
                                true));
        }
        if (game === "bluearchive") {
            const choose = SD.sel(["国服", "日服", "国际服"], ["cn", "jp", "global"].indexOf(server));
            blocks.unshift(SD.kv("服务器", [["服务器", choose]]));
            ops["切换服务器"] = {
                perform: () => {
                    server = ["cn", "jp", "global"][choose.v];
                    delete cache[game];
                    load(game, true);
                }
            };
            actions.unshift("切换服务器");
        }
        return {
            name: name,
            en: "GAME CALENDAR",
            uid: game,
            live: true,
            scrollBody: true,
            blocks: blocks,
            ops: ops,
            actions: actions
        };
    }
    function toggle(game, row, done) {
        if (!host.api || pending[game])
            return;
        const version = requests[game];
        pending[game] = true;
        host.call("/api/info/activity/completions", {
                      game: game,
                      server: game === "bluearchive" ? server : "cn",
                      name: row.name,
                      startTime: new Date(stamp(row.startTime)).toISOString(),
                      endTime: new Date(stamp(row.endTime)).toISOString(),
                      completed: done
                  }, r => {
                      if (requests[game] !== version)
                      return;
                      pending[game] = false;
                      if (r.code !== 200) {
                          host.toastText(r.message || "标记未保存");
                          return;
                      }
                      const state = cache[game], key = keyOf(row);
                      state.completed = state.completed.filter(v => v !== key);
                      if (done)
                      state.completed.push(key);
                      publish();
                  });
    }
    function load(game, force) {
        if (!host.api || !game)
            return;
        if (!force && (pending[game] || (cache[game]?.updated || 0) > Date.now() - 300000))
            return;
        const version = ++serial;
        requests[game] = version;
        pending[game] = true;
        publish();
        if (game === "arknights") {
            host.api.get("/api/info/arknights/activity", text => {
                             let r;
                             try {
                                 r = JSON.parse(text);
                             } catch (e) {
                                 r = {
                                     code: 0
                                 };
                             }
                             if (r.data)
                             r.data.source = "PRTS / SRA";
                             accept(game, version, r);
                         });
        } else if (game === "stellasora")
            host.call("/api/info/stella/activity", {}, r => {
                          if (r.data)
                          r.data.source = "星塔旅人官方公告";
                          accept(game, version, r);
                      });
        else if (game === "bluearchive") {
            const list = [];
            function batch(n) {
                host.call("/api/info/bluearchive/activity", {
                              line_type: server === "global" ? "Globle" : server.toUpperCase(),
                              page: n,
                              page_size: 100
                          }, r => {
                              if (requests[game] !== version)
                              return;
                              const rows = r.data?.data;
                              if (r.code !== 200 || !Array.isArray(rows)) {
                                  accept(game, version, {
                                             code: 500,
                                             message: r.message || "GameKee 无数据"
                                         });
                                  return;
                              }
                              rows.forEach(x => {
                                               if (x.begin_at && x.end_at)
                                               list.push({
                                                             name: x.title,
                                                             startTime: new Date(x.begin_at * 1000).toISOString(
                                                                            ),
                                                             endTime: new Date(x.end_at * 1000).toISOString()
                                                         });
                                           });
                              if (n === 1 && rows.length === 100)
                              batch(2);
                              else
                              accept(game, version, {
                                         code: 200,
                                         data: {
                                             source: "GameKee",
                                             activities: list
                                         }
                                     });
                          });
            }
            batch(1);
        } else
            activityFeed.load(game, version);
    }
    function accept(game, version, r) {
        if (requests[game] !== version)
            return;
        pending[game] = false;
        const state = cache[game] || {};
        cache[game] = state;
        if (r.code !== 200 || !Array.isArray(r.data?.activities)) {
            state.error = r.message || "活动源不可用";
            publish();
            return;
        }
        state.data = r.data;
        state.error = "";
        state.updated = Date.now();
        publish();
        if (!host.api)
            return;
        host.api.get("/api/info/activity/completions?game=" + game + "&server=" + (game === "bluearchive"
                                                                                   ? server : "cn"), text => {
                         if (requests[game] !== version)
                         return;
                         let reply;
                         try {
                             reply = JSON.parse(text);
                         } catch (e) {}
                         state.completed = reply?.code === 200 ? reply.data.map(keyOf) : null;
                         state.markError = state.completed ? "" : "完成状态读取失败，请刷新";
                         publish();
                     });
    }
}
