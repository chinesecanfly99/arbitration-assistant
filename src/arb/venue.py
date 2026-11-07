"""立案路径：把"去哪立、带什么、点哪里"变成可点的清单，而不是一段散文。

为什么值得一个模块：
- 金额和时效回答"能不能要"，路径回答"下一步动手做什么"。用户拿着 3 万块的结论却不知道
  去哪个窗口，等于没帮上忙；
- 六条路径的先后顺序本身是信息：仲裁是主路径，监察可与仲裁并行，起诉在裁决之后，
  撤销由单位发起（劳动者不用动），12348 是兜底；
- 每个动作都给 tel / copy / url 三种形态——现场演示时点一下就能打电话，比让人抄号码强。

数据全部来自 data/city/<city>.json，代码里不写死任何地址电话。
没覆盖的城市不给地址，只给统一热线，绝不拿别的城市的窗口顶替。
"""
from __future__ import annotations

import urllib.parse


def _map_url(q: str) -> str:
    return "https://uri.amap.com/search?keyword=" + urllib.parse.quote(q or "")


def _tel_action(tel: str, label: str | None = None) -> dict:
    return {"kind": "tel", "label": label or f"拨打 {tel}", "value": tel}


def build(city: dict | None = None, days_left=None, total: float | None = None) -> list[dict]:
    """返回立案路径块列表。city 为 city.City.as_dict() 的结构；None 表示口径未覆盖。"""
    blocks: list[dict] = []
    hot = (city or {}).get("hotlines") or {}
    name = (city or {}).get("city") or ""

    # ---------- 1. 仲裁申请（主路径） ----------
    if city and city.get("arbitration"):
        a = city["arbitration"]
        name_s = a.get("name") or f"{name}劳动人事争议仲裁院"
        tel = a.get("tel") or hot.get("人社") or "12333"
        acts = [_tel_action(tel)]
        if a.get("alt") and a["alt"] != tel:
            acts.append(_tel_action(a["alt"]))
        if a.get("address"):
            acts.append({"kind": "copy", "label": "复制地址", "value": a["address"]})
            acts.append({"kind": "map", "label": "一键导航", "value": _map_url(a["name"] or a["address"])})
        blocks.append({
            "stage": "① 仲裁申请（主路径）",
            "name": name_s,
            "where": a.get("address") or "以电话确认的窗口为准",
            "hours": a.get("hours") or "",
            "note": (
                f"{name}：仲裁不收费；受理后 45 日内审结、复杂可延 15 日。"
                "申请书按被申请人人数 +1 份准备，现场可领格式表。"
            ),
            "actions": acts,
        })
    else:
        blocks.append({
            "stage": "① 仲裁申请（主路径）",
            "name": "劳动合同履行地或用人单位所在地的劳动人事争议仲裁委员会",
            "where": "你实际干活的地方 / 公司注册地，二者选一",
            "hours": "",
            "note": (
                "你所在城市的口径还没收录，所以这里不写具体窗口，避免给错地址。"
                "先打 12333 问清管辖，再去窗口；仲裁不收费，别信「代办立案」。"
            ),
            "actions": [_tel_action("12333")],
        })

    # ---------- 2. 网上预申请 ----------
    if city and city.get("online"):
        blocks.append({
            "stage": "② 网上预申请（能少跑一趟）",
            "name": f"{name}线上入口",
            "where": "见下方「入口说明」",
            "hours": "",
            "note": city["online"] + "。网上提交后仍须到窗口核验材料原件。",
            "actions": [
                {"kind": "copy", "label": "复制入口说明", "value": city["online"]},
                _tel_action(hot.get("人社") or "12333", "打 12333 问进度"),
            ],
        })

    # ---------- 3. 起诉（不服裁决） ----------
    court_days = f"你的时效还剩 {days_left} 天；" if isinstance(days_left, int) else ""
    blocks.append({
        "stage": "③ 起诉（不服裁决，仲裁之后）",
        "name": "人民法院（劳动争议一审）",
        "where": "微信小程序「人民法院在线服务」可网上立案",
        "hours": "",
        "note": (
            court_days + "裁决书送达之日起 15 日内向法院起诉；一裁终局案件劳动者同样可起诉，"
            "单位只能申请撤销。诉讼费 10 元，劳动争议可申请缓交。"
        ),
        "actions": [_tel_action(hot.get("法院诉讼服务") or "12368", "诉讼服务热线 12368")],
    })

    # ---------- 4. 单位申请撤销（只是告知，劳动者不用做） ----------
    line = (city or {}).get("one_final_award_threshold")
    blocks.append({
        "stage": "④ 单位申请撤销（一裁终局，你不需要操作）",
        "name": f"{name}中级人民法院" if name else "用人单位所在地中级人民法院",
        "where": "由单位提出，你只需应诉",
        "hours": "",
        "note": (
            "一裁终局案件中，单位有证据证明存在法定情形的，可自收到裁决书之日起 30 日内向中院申请撤销。"
            + (f"本案标的 {total:,.0f} 元、当地一裁终局线 {line:,.0f} 元。" if total and line else "")
            + "这一条列出来只是让你知道对方还有什么牌，不用你去做。"
        ),
        "actions": [{"kind": "text", "label": "该路径由单位发起，你不需要做", "value": "info"}],
    })

    # ---------- 5. 欠薪快速通道 ----------
    blocks.append({
        "stage": "⑤ 欠薪快速通道（可与仲裁并行）",
        "name": "劳动保障监察（人社部门）",
        "where": "当地人社局劳动保障监察机构",
        "hours": "",
        "note": (
            "拖欠工资、不签合同、超时加班都可以向监察投诉（12333）。"
            "监察走行政责令，通常比仲裁快；但监察不处理经济补偿和赔偿金，那部分仍要走仲裁。"
            "两条路可以同时走，不冲突。"
        ),
        "actions": [_tel_action(hot.get("人社") or "12333", "监察投诉 12333")],
    })

    # ---------- 6. 兜底 ----------
    blocks.append({
        "stage": "⑥ 兜底咨询 / 法律援助",
        "name": "公共法律服务热线 / 法律援助中心",
        "where": "拨 12348，或到区县法律援助中心面谈",
        "hours": "",
        "note": (
            "本页面不是律师意见。金额较大、涉及违法解除或竞业限制的，建议先打 12348 问一遍；"
            "符合条件的（低收入、请求支付劳动报酬等）可以申请免费法律援助，由援助律师代理仲裁。"
        ),
        "actions": [_tel_action(hot.get("法律援助") or "12348", "法律援助 12348")],
    })
    return blocks


def summary(blocks: list[dict]) -> str:
    if not blocks:
        return ""
    return (
        f"共 {len(blocks)} 条路径：① 是主路径，② 能少跑一趟，⑤ 可以和仲裁同时走，"
        "④ 由单位发起（了解即可），⑥ 是兜底。"
    )
