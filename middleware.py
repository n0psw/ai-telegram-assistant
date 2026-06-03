import time
import logging
from collections import defaultdict
from config import RATE_LIMIT_MESSAGES, RATE_LIMIT_WINDOW

logger = logging.getLogger(__name__)

user_message_times: dict[int, list[float]] = defaultdict(list)


def check_rate_limit(user_id: int) -> bool:
    now = time.time()
    times = user_message_times[user_id]
    user_message_times[user_id] = [t for t in times if now - t < RATE_LIMIT_WINDOW]

    if len(user_message_times[user_id]) >= RATE_LIMIT_MESSAGES:
        logger.warning(f"Rate limit exceeded for user {user_id}")
        return False

    user_message_times[user_id].append(now)
    return True
