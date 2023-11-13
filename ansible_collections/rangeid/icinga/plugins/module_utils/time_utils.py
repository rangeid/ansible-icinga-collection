import re

class time_utils:
    @staticmethod
    def convert_duration(duration_str):
        unit_mapping = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400
        }

        total_seconds = 0
        pattern = r'(\d+)([dhms])'
        matches = re.findall(pattern, duration_str)

        for value, unit in matches:
            total_seconds += int(value) * unit_mapping[unit]

        return total_seconds
