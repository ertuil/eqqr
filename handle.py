import asyncio
import logging

import math
import time
import datetime
from typing import Any, Dict, Tuple
from geopy.distance import geodesic

from source import source_cene, source_sc, source_fj
import notify
import config


def get_distance(loc1: Tuple[float, float], loc2: Tuple[float, float]) -> float:
    new_loc1 = (float(loc1[0]), float(loc1[1]))
    new_loc2 = (float(loc2[0]), float(loc2[1]))
    return geodesic(new_loc1, new_loc2).km


def get_arrivetime(distance: float, report_time: str) -> datetime:
    timeArray = time.strptime(report_time, "%Y-%m-%d %H:%M:%S")
    timeStamp = time.mktime(timeArray)

    diff_time = datetime.timedelta(seconds=distance / 4)
    arrivetime = datetime.datetime.fromtimestamp(timeStamp) + diff_time
    return arrivetime


def get_lintensity(distance: float, magunitude: str) -> float:
    localintensity = 0.92 + 1.63 * float(magunitude) - 3.49 * math.log10(distance)
    if localintensity <= 0:
        localintensity = 0.0
    elif localintensity < 12:
        localintensity = int(localintensity * 10) / 10.0  # 保留1位小数
    elif localintensity >= 12:
        localintensity = 12.0
    return localintensity


async def serve():
    logger = logging.getLogger("eqqr.handle")
    while True:
        try:
            ret = await asyncio.gather(
                source_cene(),
                source_sc(),
                source_fj(),
            )
        except Exception as e:
            logger.error(f"Failed to get report: {e}")
            await asyncio.sleep(1)
            continue

        for report in ret:
            if report is None:
                continue
            try:
                await handle_report(report)
            except Exception as e:
                logger.error(f"Failed to handle report {report}: {e}")

        await asyncio.sleep(1)


async def handle_report(report):
    logger = logging.getLogger("eqqr.handle.report")
    for user_name in config.config["users"]:
        user_info = config.config["users"][user_name]
        location = user_info["location"]
        loc1 = (location["latitude"], location["longitude"])
        loc2 = (report["latitude"], report["longitude"])

        magnitude = float(report["magnitude"])
        dist = get_distance(loc1, loc2)
        lintensity = get_lintensity(dist, report["magnitude"])
        arrivetime = get_arrivetime(dist, report["time"])

        full_report = report.copy()
        full_report["distance"] = dist
        full_report["local_lintensity"] = lintensity
        full_report["arrivetime"] = arrivetime.strftime("%Y-%m-%d %H:%M:%S")
        full_report["user"] = user_name

        if dist < 200 or (dist <= 1000 and magnitude > 2) or (config.config["test"]):
            logger.info(f"Notify {user_name} with {full_report}")
            await handle_notify(user_info, full_report)
        else:
            logger.debug(f"Skip notify {user_name} with {full_report} for long distance")


async def format_message(
    user_info: Dict[str, Any], full_report: Dict[str, Any]
) -> Tuple[str, str]:
    latitude_str = (
        "北纬"
        if float(full_report["latitude"]) > 0
        else "南纬"
    )
    latitude_str = latitude_str + str(abs(float(full_report["latitude"])))
    longitude_str = (
        "东经"
        if float(full_report["longitude"]) > 0
        else "西经"
    )
    longitude_str = longitude_str + str(abs(float(full_report["longitude"])))
    msg = f"地震警告-{full_report['type']}: {full_report['time']} 在{full_report['location']}（{latitude_str}，{longitude_str}）发生了{full_report['magnitude']}级地震, 震源深度{full_report['depth']}千米, 震中位置距您{full_report['distance']:.1f}千米, 预计{full_report['arrivetime']}到达, 预计您当地烈度为{full_report['local_lintensity']}级。数据来源：{full_report['source']}。"

    subject = f"地震警告-{full_report['type']}: {full_report['location']} {full_report['magnitude']}级地震"
    return subject, msg


async def handle_notify(user_info: Dict[str, Any], full_report: Dict[str, Any]):
    logger = logging.getLogger("eqqr.handle.notify")
    try:
        subject, msg = await format_message(user_info, full_report)
    except Exception as e:
        logger.error(f"Failed to format message: {e}")
        return

    config_user_message = user_info.get("contact", None)
    if config_user_message is None:
        logger.warning(f"User {full_report['user']} has no message configured")
        return

    notify_list = []

    mail_list = config_user_message.get("mail", [])
    if len(mail_list) > 0:
        if notify.mail_notifier is None:
            logger.error("Mail notifier is not initialized")

        notify_list.append(notify.mail_notifier.emit(msg, mail_list, subject))

    push_list = config_user_message.get("pushdeer", [])
    if len(push_list) > 0:
        if notify.pushdeer_notifier is None:
            logger.error("Push notifier is not initialized")
        push_msg = subject +"%0A" +msg
        for push_key in push_list:
            notify_list.append(notify.pushdeer_notifier.emit(push_msg, push_key))

    tg_list = config_user_message.get("tg", [])
    if len(tg_list) > 0:
        if notify.tg_notifier is None:
            logger.error("Telegram notifier is not initialized")

        for chatid in tg_list:
            notify_list.append(notify.tg_notifier.emit(msg, chatid))

    alisms_list = config_user_message.get("phone", [])
    if len(alisms_list) > 0:
        if notify.alisms_notifier is None:
            logger.error("Alisms notifier is not initialized")

        notify_list.append(notify.alisms_notifier.emit(alisms_list, "SMS_465374479", {"node": subject}))

    try:
        await asyncio.gather(*notify_list)
    except Exception as e:
        logger.error(f"Failed to notify user: {e}")
        return
    logger.info(f"Notify user {full_report['user']} successful")
