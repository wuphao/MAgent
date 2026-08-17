class Solution(object):
    def groupAnagrams(self, strs):
        res = []
        hash_map = {}
        for str in strs:
            c = [0]*26
            for ch in str:
                c[ord(ch)-ord('a')]+=1
            if tuple(c) not in hash_map:
                hash_map[tuple(c)] = [str]
            else:
               hash_map[tuple(c)].append(str)
        return list(hash_map.values())
    
    def maxArea(self, height):
        """
        :type height: List[int]
        :rtype: int
        """
        res = 0
        i = 0
        j = len(height)-1
        while i<=j :
            if height[i]<height[j]:
                h = (j-i)* height[j]
                j-=1
                if h>res :
                    res=h
            else :
                h = (j - i) * height[i]
                i+=1
                if h>res :
                    res=h

        return res
    
    def threeSum(self, nums):
        nums.sort()
        n = len(nums)
        res = []
        if n < 3:
            return res
        for i in range(n):
            if i > 0 and nums[i] == nums[i-1]:
                continue
            j, k = i + 1, n - 1
            while j < k:
                total = nums[i] + nums[j] + nums[k]
                if total == 0:
                    res.append([nums[i], nums[j], nums[k]])
                    j += 1
                    k -= 1
                    while j < k and nums[j] == nums[j-1]:
                        j += 1
                    while j < k and nums[k] == nums[k+1]:
                        k -= 1
                elif total < 0:
                    j += 1
                else:
                    k -= 1
        return res
    
    def trap(self, height):
        """
        :type height: List[int]
        :rtype: int
        """
        n = len(height)
        res = 0
        right_high = []
        right_high[n-1] = 0
        i = n-2
        mr= height[n-1]
        while i > 0 :
            right_high[i] = max(height[i-1],mr)
            if right_high[i] is not mr :
                mr = right_high[i]
            i-=1
        
        j = 1
        ml = height[0]
        lift_high = []
        while j < n :
            lift_high[j] = max(height[j-1],ml)
            if lift_high[j] is not ml:
                ml = lift_high[j]
            j+=1  
        
        for i in (1,n-1):
            temp = min(lift_high[i],right_high[i])
            if temp > height[i]:
                res += (temp-height[i])
        return res



