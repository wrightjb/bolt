'''
Created on Jun 22, 2012
quick description and documentation in attached readme file. 
@author: colinwinslow
'''
import cluster_util
from cluster_util import ClusterParams
import numpy as np
import heapq
from cluster import dbscan,clustercost
from copy import copy




def main():
    print "Sample run of line detecton on Blockworld: \n"
    np.seterr(all='raise')
    print "scene 14, step 8"
    result = findChains(util.get_objects(14, 8))
    print result
    print  "cost: ", np.round(result[-1],4),"\t",map(util.lookup_objects,result[:-1])
        
        

    

def sceneEval(inputObjectSet,params = ClusterParams(2,0.9,3,0.05,0.1,1,0,11,False)):
    
    '''
    find the clusters
    evaulate the inside of the clusters as lines to see if they'd be better as lines than clusters
    evaluate the outside of clusters for lines
    concatenate the lists of clusters and lines
    evaluate the whole thing with bundle search
    '''
    reducedObjectSet = copy(inputObjectSet)
    
    clusterCandidates = clustercost(dbscan(np.array(map(lambda x: (x.position,x.id),inputObjectSet))))
    
    innerLines = []
    #search for lines inside large clusters
    if params.attempt_dnc==True:
        for cluster in clusterCandidates[1]:

            innerObjects = []
            for id in cluster:
                for x in inputObjectSet:
                    if x.id == id:
                        innerObjects.append(x)
            innerChains = findChains(innerObjects,params)
            for thing in innerChains:
                innerLines.append(thing)
            
        #remove core clusters
        for cluster in clusterCandidates[0]:
            for id in cluster:
                for x in reducedObjectSet:
                    if x.id == id:
                        reducedObjectSet.remove(x)

    lineCandidates = findChains(reducedObjectSet,params)
    
    allCandidates = clusterCandidates[0]+clusterCandidates[1] + lineCandidates + innerLines
    groupDictionary = dict()
    for i in allCandidates:
        groupDictionary[i.uuid]=i
    evali = bundleSearch(cluster_util.totuple(inputObjectSet), allCandidates, params.allow_intersection, params.beam_width)   
    #find the things in evali that aren't in the dictionary ,and make a singleton group out of them, and add it to the output
    output = map(lambda x: groupDictionary.get(x),evali)
    return output
    

def findChains(inputObjectSet, params ):
    '''finds all the chains, then returns the ones that satisfy constraints, sorted from best to worst.'''
  
    bestlines = []
    explored = set()
    pairwise = cluster_util.find_pairs(inputObjectSet)
    pairwise.sort(key=lambda p: cluster_util.findDistance(p[0].position, p[1].position),reverse=False)
    for pair in pairwise:
        start,finish = pair[0],pair[1]
        if frozenset([start.id,finish.id]) not in explored:
            result = chainSearch(start, finish, inputObjectSet,params)
            if result != None: 
                bestlines.append(result)
                s = map(frozenset,cluster_util.find_pairs(result[0:len(result)-1]))
                
                map(explored.add,s)

               
    verybest = []
    costSum = 0
    for line in bestlines:
        if len(line)>params.min_line_length:
            verybest.append(line)
    verybest.sort(key=lambda l: len(l),reverse=True)
    costs = map(lambda l: l.pop()+2,verybest)
    data = np.array(map(lambda x: (x.position,x.id),inputObjectSet))
    output = []
    for i in zip(costs,verybest):
        output.append(cluster_util.LineBundle(i[1],i[0]))
    return output
    
            
def chainSearch(start, finish, points,params):
    node = Node(start, -1, [], 0,0)
    frontier = PriorityQueue()
    frontier.push(node, 0)
    explored = set()
    while frontier.isEmpty() == False:
        node = frontier.pop()
        if node.getState().id == finish.id:
            path = node.traceback()
            path.insert(0, start.id)
            return path
        explored.add(node.state.id)
        successors = node.getSuccessors(points,start,finish,params)
        for child in successors:
            if child.state.id not in explored and frontier.contains(child.state.id)==False:
                frontier.push(child, child.cost)
            elif frontier.contains(child.state.id) and frontier.pathCost(child.state.id) > child.cost:
                frontier.push(child,child.cost)     
        
#cost functions

def oldAngleCost(a, b, c):
    '''angle cost of going to c given we came from ab'''
    abDir = b - a
    bcDir = c - b
    difference = cluster_util.findAngle(abDir, bcDir)
    if np.isnan(difference): return 0
    else: return np.abs(difference)
    
def angleCost(a, b, c, d):
    '''prefers straighter lines'''
    abDir = b - a
    cdDir = d - c
    difference = cluster_util.findAngle(abDir, cdDir)
    if np.isnan(difference): return 0
    else: return np.abs(difference)
    
def distVarCost(a, b, c):
    #np.seterr(all='warn')
    '''prefers lines with less variance in their spacing'''
    abDist = cluster_util.findDistance(a, b)
    bcDist = cluster_util.findDistance(b, c)
    if bcDist==0:
        #shouldn't ever occur, but prevents undefined data while debugging
        return 0
    return np.abs(np.log2((1/abDist)*bcDist))

def distCost(current,step,start,goal):
    '''prefers dense lines to sparse ones'''
    stepdist = cluster_util.findDistance(current, step)
    totaldist= cluster_util.findDistance(start, goal)
    return stepdist**2/totaldist**2

def bundleSearch(scene, groups, intersection = 0,beamwidth=10):
    global allow_intersection 
    allow_intersection = intersection
    
    print "number of groups:",len(groups)
    expanded = 0
    singletonCost = 1

    for i in scene:
        groups.append(cluster_util.SingletonBundle([i[0]],singletonCost))
        
    node = BNode(frozenset(), -1, [], 0)
    frontier = BundlePQ()
    frontier.push(node, 0)
    explored = set()
    while frontier.isEmpty() == False:
        node = frontier.pop()
        expanded += 1
        if node.getState() >= frozenset(map(lambda x:x[0],scene)):
            path = node.traceback()
            print "scene evaluation expanded",expanded,"nodes with beam width of ",beamwidth
            break
        explored.add(node.state)
        successors = node.getSuccessors(scene,groups)
        successors.sort(key= lambda s: s.gainratio,reverse=True)
        successors = successors[0:beamwidth]
        for child in successors:
            if child.state not in explored and frontier.contains(child.state)==False:
                frontier.push(child, child.cost)
            elif frontier.contains(child.state) and frontier.pathCost(child.state) > child.cost:
                
                frontier.push(child,child.cost)        
    return path
    
class Node:
    def __init__(self, state, parent, action, cost,qCost):
        self.state = state
        self.parent = parent
        self.action = action
        self.icost = cost
        self.iqcost = qCost
        if parent != -1:
            self.cost = parent.cost + cost
            self.qCost = parent.qCost + qCost
        else:
            self.cost=cost
            self.qCost = qCost
            
    def getState(self):
        return self.state
    
    def getSuccessors(self, points,start,finish,params):
        
        out = []
        if self.parent == -1: 
            for p in points:
                if self.state.id != p.id and finish.id!=p.id: 
                    aCost = angleCost(self.state.position,finish.position, self.state.position, p.position)
                    dCost =distCost(self.state.position,p.position,start.position,finish.position)
                    if aCost <= params.angle_limit and dCost < 1: # prevents it from choosing points that overshoot the target.
                        normA = params.anglevar_weight*(aCost/params.angle_limit)
                        distanceCost = dCost
                        qualityCost = normA/params.anglevar_weight
                        out.append(Node(p,self,p.id, distanceCost,qualityCost))
        else:
            out = []
            for p in points:
                if self.state.id != p.id: 
                    vCost = distVarCost(self.parent.state.position, self.state.position, p.position)
#                    print self.parent.state.position,self.state.position,p.position,"--",vCost/params.chain_distance_limit
                    
                    aCost = oldAngleCost(self.parent.state.position,self.state.position,p.position)
                    dCost = distCost(self.state.position,p.position,start.position,finish.position)
#                    print "dcost",dCost
                    if aCost <= params.angle_limit and dCost <= 1 and vCost/params.chain_distance_limit <= 1:
                        normV = params.distvar_weight*(vCost/params.chain_distance_limit)
                        normA = params.anglevar_weight*(aCost/params.angle_limit)
                        qualityCost = (normA+normV)/(params.distvar_weight+params.anglevar_weight)
                        out.append(Node(p,self,p.id,dCost,qualityCost))
        
        return out

    def traceback(self):
        solution = []
        node = self
        while node.parent != -1:
            solution.append(node.action)

            node = node.parent
        cardinality = len(solution)-1 #exclude the first node, which has cost 0
        cost = self.qCost#/cardinality
        solution.reverse()
        solution.append(cost)

        return solution

class BNode:
    def __init__(self, state, parent, action, cost):
        self.state = state
        self.parent = parent
        self.action = action
        self.cost = cost
        if parent != -1:
            self.cost = parent.cost + cost
        else:
            self.cost=cost
        self.gain = len(self.state)-self.cost

        if len(self.state)>0:
            self.gainratio = self.gain/len(self.state)
        else: self.gainratio = 0

            
    def getState(self):
        return self.state
    
    def getSuccessors(self, points,groups):
        successors = []

        for g in groups:

            if len(self.state.intersection(g.members))<=allow_intersection:
                asd=BNode(self.state.union(g.members),self,cluster_util.successorTuple(g.cost,g.members,g.uuid),g.cost)
                if asd.gain > 0:
                    successors.append(asd)
        return successors
        

    def traceback(self):
        solution = []
        node = self
        while node.parent != -1:
#            solution.append(node.action[1])
            solution.append(node.action.uuid)

            node = node.parent
        cardinality = len(solution)-1 #exclude the first node, which has cost 0
        cost = self.cost#/cardinality
        solution.reverse()
        #solution.append(cost)

        return solution
    
class PriorityQueue:
    '''stolen from ista 450 hw ;)'''

    def  __init__(self):  
        self.heap = []
        self.dict = dict()
    
    def push(self, item, priority):
        pair = (priority, item)
        heapq.heappush(self.heap, pair)
        self.dict[item.state.id]=priority
    
    def contains(self,item):
        return self.dict.has_key(item)
    
    def pathCost(self,item):
        return self.dict.get(item)

    def pop(self):
        (priority, item) = heapq.heappop(self.heap)
        return item
        
    def isEmpty(self):
        return len(self.heap) == 0
    
class BundlePQ:

    def  __init__(self):  
        self.heap = []
        self.dict = dict()
    
    def push(self, item, priority):
        pair = (priority, item)
        heapq.heappush(self.heap, pair)
        self.dict[item.state]=priority
    
    def contains(self,item):
        return self.dict.has_key(item)
    
    def pathCost(self,item):
        return self.dict.get(item)

    def pop(self):
        (priority, item) = heapq.heappop(self.heap)
        return item
        
    def isEmpty(self):
        return len(self.heap) == 0


if __name__ == '__main__': main()
