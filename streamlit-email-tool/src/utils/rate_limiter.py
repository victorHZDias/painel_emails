from datetime import datetime, timedelta
import time

class RateLimiter:
    def __init__(self, max_emails_per_day=500, max_emails_per_minute=10):
        self.max_emails_per_day = max_emails_per_day
        self.max_emails_per_minute = max_emails_per_minute
        self.emails_sent_today = 0
        self.start_time = datetime.now()
        self.last_email_time = None

    def can_send_email(self):
        now = datetime.now()
        if now.date() != self.start_time.date():
            self.reset_daily_limit()
        
        if self.emails_sent_today < self.max_emails_per_day:
            if self.last_email_time is None:
                return True
            elif (now - self.last_email_time).total_seconds() >= 6:  # 60 seconds / 10 emails
                return True
        return False

    def reset_daily_limit(self):
        self.emails_sent_today = 0
        self.start_time = datetime.now()

    def send_email(self):
        if self.can_send_email():
            self.emails_sent_today += 1
            self.last_email_time = datetime.now()
            return True
        return False

    def wait_for_next_email(self):
        if self.last_email_time is not None:
            time_to_wait = 6 - (datetime.now() - self.last_email_time).total_seconds()
            if time_to_wait > 0:
                time.sleep(time_to_wait)