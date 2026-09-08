class TreeNode(object):
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
class Solution:
    def isValidBST(self, root):
        stack = []
        inorder = float('-inf')   

        while stack or root:
            while root:
                stack.append(root)
                root = root.left
            root = stack.pop()
            if root.val <= inorder:
                return False
            inorder = root.val
            root = root.right

        return True

        
def main():
    solution = Solution()
    print(solution.groupAnagrams(["eat", "tea", "tan", "ate", "nat", "bat"]))
    print(solution.maxArea([1,8,6,2,5,4,8,3,7]))
    print(solution.threeSum([-1,0,1,2,-1,-4]))
    print(solution.trap([0,1,0,2,1,0,1,3,2,1,2,1]))


if __name__ == "__main__":
    main()