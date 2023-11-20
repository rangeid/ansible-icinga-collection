import re

class time_utils:
    @staticmethod
    def convert_duration(duration_str):
        """
        Convert a duration string to the equivalent number of seconds.

        Args:
            duration_str (str): A string representing a duration in the format "NdNhNmNs", where N is a number and d/h/m/s represent days, hours, minutes, and seconds respectively.

        Returns:
            int: The number of seconds equivalent to the input duration.

        Example:
            >>> convert_duration('1d2h30m')
            95400
        """
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
