class TreeNode(object):
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right

class Solution(object):
    def inorderTraversal(self, root):
        res = []
        def dfs(node):
            if not node:
                return
            dfs(node.left)        
            res.append(node.val)
            dfs(node.right)      
        dfs(root)
        return res

         
def main():
   s = Solution()
   test = [4,2,0,3,2,5]
   print(s.trap(test))

if __name__ == "__main__":
    main()