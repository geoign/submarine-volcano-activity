"""Fixed vocabularies of the public tables and the translations of the monitor's Japanese labels."""

# Public classes of an episode, most significant first. The order is used by the map.
CLASSES = ["known", "likely", "possible", "recurrent", "airborne", "undetermined", "nonvolcanic", "unreviewed"]

# Classes shown by default (everything that was not dismissed).
ACTIVE_CLASSES = ["known", "likely", "possible"]

PHENOMENA = {
    "dw": "discoloured water",
    "fl": "floating matter",
    "nl": "new land",
    "th": "thermal anomaly",
    "sc": "scene colour",
    "ap": "airborne band",
}

CAUSES = [
    "cloud", "cloud_shadow", "sun_glint", "reef_or_shoal", "land_or_surf", "land_or_ice", "bloom",
    "sediment_plume", "ship_wake", "sensor_artifact", "neighbour_eruption", "persistent", "other",
]

DEPTH_CLASS = {
    "浅（<200 m）": "lt200",
    "中（200–500 m）": "200-500",
    "深（500–1000 m）": "500-1000",
    "不明（海面付近の火口）": "near_surface",
    "海面付近（カルデラ内に陸地あり）": "near_surface_island",
    "不明（2026年噴火で海面に軽石・変色水）": "unknown",
}

COVERAGE = {
    "S2+Landsat": "s2+landsat",
    "S2のみ": "s2",
    "Landsatのみ": "landsat",
    "なし": "lowres_only",
    "": "lowres_only",
}

# zone_type_ja of aoi/zones.csv
ZONE_TYPE = {
    "山頂（GVP座標）": "summit (GVP coordinates)",
    "カルデラ全域（縁ポリゴン重心）": "whole caldera (centroid of the rim polygon)",
    "山頂/火口（GVP座標）": "summit or vent (GVP coordinates)",
    "山頂": "summit",
    "火山島周辺の海底": "seafloor around the volcanic island",
    "熱水域（InterRidge座標）": "hydrothermal field (InterRidge coordinates)",
    "火口": "vent",
    "カルデラ全域": "whole caldera",
    "火口（新島）": "vent (new island)",
    "中央火口丘": "central cone",
    "カルデラ・中央火口丘": "caldera and central cone",
    "山頂（双峰）": "summit (twin peaks)",
    "1831年火口": "vent of 1831",
    "1846/1867年噴火地点": "eruption site of 1846 and 1867",
    "カルデラ縁山頂": "summit on the caldera rim",
    "主火口": "main vent",
    "火口・山頂": "vent and summit",
    "火山群全域": "whole volcanic group",
    "山頂火口": "summit crater",
    "地震群の警戒域": "zone on an earthquake cluster (centroid of the epicentres)",
    "カルデラ内スコリア丘2個": "two scoria cones inside the caldera",
    "カルデラ・火口丘": "caldera and cone",
    "後カルデラ中央火口丘": "post-caldera central cone",
    "卓状山頂の火山体": "flat-topped edifice",
    "3火口丘（北:2010年火口,南:最浅,東）": "three cones (north: vent of 2010, south: shallowest, east)",
    "WNW-ESE割れ目尾根": "WNW-ESE fissure ridge",
    "火山島・カルデラ": "volcanic island and caldera",
    "火山島周辺": "around the volcanic island",
    "海底噴火地点": "submarine eruption site",
    "群島全域": "whole island group",
    "海峡全域": "whole strait",
    "後カルデラ円錐火山（カルデラ東部）": "post-caldera cone (eastern caldera)",
    "カルデラ南縁の岩礁": "reef on the southern caldera rim",
    "火口丘群(A-G)": "group of cones (A to G)",
    "後カルデラ火山体（カルデラ北東縁）": "post-caldera edifice (north-eastern caldera rim)",
    "GVP座標": "GVP coordinates",
    "火口丘": "cone",
    "カルデラ": "caldera",
    "ガス噴出火口・火山体": "degassing vent and edifice",
    "2026年噴火地点（NE・SW火口）": "eruption site of 2026 (NE and SW vents)",
}

# Labels of the classes, for texts the build writes itself.
CLASS_EN = {"known": "documented eruption period", "likely": "likely volcanic", "possible": "possibly volcanic",
            "recurrent": "recurrent discolouration", "airborne": "airborne band", "undetermined": "undetermined",
            "nonvolcanic": "not volcanic", "unreviewed": "not reviewed"}
CLASS_JA = {"known": "既知の噴火期間", "likely": "火山性の可能性が高い", "possible": "火山性の可能性あり",
            "recurrent": "繰り返す変色", "airborne": "大気中の帯", "undetermined": "判断がつかない",
            "nonvolcanic": "火山性ではない", "unreviewed": "未判定"}

# Who looked at an episode (column `review_status`), after the status of earthquake catalogues:
# the author's own verdict, an AI-assisted review, or nothing but the screening and a date match.
REVIEW_STATUS = ["human-reviewed", "ai-reviewed", "automatic"]

# Where the class of an episode comes from (column `basis`).
BASES = ["catalogue", "ai_review", "ai_review_partial", "rule", "lead_review", "owner", ""]

# verdict vocabulary of the monitor (python -m submvolc verdict)
VERDICT_CLASS = {
    "volcanic_likely": "likely",
    "volcanic_possible": "possible",
    "non_volcanic": "nonvolcanic",
    "undetermined": "undetermined",
}
