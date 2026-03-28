from collections.abc import Iterable


class OutlierCleanTool:
    """Simple winsorization to avoid extreme sample impact."""

    @staticmethod
    def winsorize(values: Iterable[float], lower_q: float = 0.05, upper_q: float = 0.95) -> list[float]:
        nums = sorted(float(v) for v in values)
        if not nums:
            return []
        if len(nums) < 4:
            return nums
        lower_idx = max(0, int((len(nums) - 1) * lower_q))
        upper_idx = min(len(nums) - 1, int((len(nums) - 1) * upper_q))
        low = nums[lower_idx]
        high = nums[upper_idx]
        return [max(min(v, high), low) for v in nums]

