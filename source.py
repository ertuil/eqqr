import datetime
import time
import traceback
import httpx
import logging
import config
import json


cene_old_md5 = ""
sc_old_eventid = ""
fj_old_eventid = ""
meihuan_old_eventid = ""


async def source_cene():
    global cene_old_md5
    logger = logging.getLogger("eqqr.source.cene")
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get("https://api.wolfx.jp/cenc_eqlist.json")
        if response.status_code != 200:
            logger.error(f"Failed to get data from source: {response.status_code}")
            return None

        try:
            new_md5 = response.json()["md5"]
            if cene_old_md5 == "" and not config.config["test"]:
                cene_old_md5 = new_md5
            if new_md5 == cene_old_md5:
                logger.debug("No new data from CENE")
                return None

            cene_old_md5 = new_md5
            logger.info("Get new data from CENE")

            new_report = response.json()["No1"]
            etype = "正式测定" if new_report["type"] == "reviewed" else "自动测定"

            ret = {
                "time": new_report["time"],
                "source": "中国地震台网",
                "type": etype,
                "location": new_report["location"],
                "magnitude": new_report["magnitude"],
                "depth": new_report["depth"],
                "latitude": new_report["latitude"],
                "longitude": new_report["longitude"],
                "intensity": new_report["intensity"],
            }
            logger.info(ret)
            return ret
        except Exception as e:
            logger.error(f"Failed to parse data from source: {e}")
            return None


async def source_fj():
    global fj_old_eventid
    logger = logging.getLogger("eqqr.source.fj")
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get("https://api.wolfx.jp/fj_eew.json")
        if response.status_code != 200:
            logger.error(f"Failed to get data from source: {response.status_code}")
            return None

        try:
            report = response.json()
            new_event_id = report["EventID"]
            if fj_old_eventid == "" and not config.config["test"]:
                fj_old_eventid = new_event_id
            if fj_old_eventid == new_event_id:
                logger.debug("No new data from SC")
                return None
            fj_old_eventid = new_event_id
            logger.info("Get new data from SC")

            report = response.json()
            ret = {
                "time": report["OriginTime"],
                "source": "福建省地震局",
                "type": "地震预测",
                "location": report["HypoCenter"],
                "magnitude": str(report["Magunitude"]),
                "depth": "未知",
                "latitude": str(report["Latitude"]),
                "longitude": str(report["Longitude"]),
                "intensity": "未知",
            }
            logger.info(ret)
            return ret
        except Exception as e:
            logger.error(f"Failed to parse data from source: {e}")
            return None


async def source_sc():
    global sc_old_eventid
    logger = logging.getLogger("eqqr.source.sc")
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get("https://api.wolfx.jp/sc_eew.json")
        if response.status_code != 200:
            logger.error(f"Failed to get data from source: {response.status_code}")
            return None

        try:
            report = response.json()
            new_event_id = report["EventID"]
            if sc_old_eventid == "" and not config.config["test"]:
                sc_old_eventid = new_event_id
            if sc_old_eventid == new_event_id:
                logger.debug("No new data from SC")
                return None
            sc_old_eventid = new_event_id
            logger.info("Get new data from SC")

            report = response.json()
            ret = {
                "time": report["OriginTime"],
                "source": "四川省地震局",
                "type": "地震预测",
                "location": report["HypoCenter"],
                "magnitude": str(report["Magunitude"]),
                "depth": str(report.get("Depth", "未知")),
                "latitude": str(report["Latitude"]),
                "longitude": str(report["Longitude"]),
                "intensity": str(report["MaxIntensity"]),
            }
            logger.info(ret)
            return ret
        except Exception as e:
            logger.error(f"Failed to parse data from source: {e}")
            return None


async def source_chinaeew():
    global meihuan_old_eventid
    logger = logging.getLogger("eqqr.source.chinaeew")
    async with httpx.AsyncClient(timeout=5) as client:
        start_ts = int((datetime.datetime.now() - datetime.timedelta(days=7)).timestamp() * 1000)
        response = await client.get(f"https://mobile-new.chinaeew.cn/v1/earlywarnings?start_at={start_ts}&updates=")
        if response.status_code != 200:
            logger.error(f"Failed to get data from source: {response.status_code}")
            return None
        
        try:
            response = response.json()
        except Exception as e:
            logger.error(f"Failed to parse data from source: {e} 1")
            return None

        try:
            code = response["code"]
            if code != 0:
                logger.error(f"Failed to get data from source: code {code}")
                return None
            
            reports = response["data"]
            if len(reports) == 0:
                logger.debug("No new data from Chinaeew")
                return None
            report = reports[0]
           
            new_event_id = report["eventId"]
            if meihuan_old_eventid == "" and not config.config["test"]:
                meihuan_old_eventid = new_event_id
            if meihuan_old_eventid == new_event_id:
                logger.debug("No new data from Chinaeew")
                return None
            meihuan_old_eventid = new_event_id
            logger.info("Get new data from Chinaeew")

            start_ts = float(report["startAt"]) / 1000
            print(start_ts)
            start_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(start_ts))
            ret = {
                "time": start_time,
                "source": report["sourceType"],
                "type": "地震预警",
                "location": report["epicenter"],
                "magnitude": str(round(report["magnitude"], 2)),
                "depth": str(report.get("depth", "未知")),
                "latitude": str(round(report["latitude"], 2)),
                "longitude": str(round(report["longitude"], 2)),
                "intensity": "",
            }
            logger.info(ret)
            return ret
        except Exception as e:
            traceback.print_exc()
            logger.error(f"Failed to parse data from source: {e}")
            return None
