#
# @file S3DET.py
# @author Mingjie Liu
# @date 10/02/2019
# @brief The class for generating system symmetry constraints using graph similarity
#
import magicalFlow
import networkx as nx
from itertools import combinations
import GraphSim
import matplotlib.pyplot as plt

clk_set = {"clk", "clksb", "clks_boost", "clkb", "clkbo"}
vss_set = {"gnd", "vss", "vss_sub", "vrefn", "vrefnd", "avss", "dvss", "vss_d"}
vdd_set = {"vdd", "vdd_and", "vdd_c", "vdd_comp", "vdd_gm", "vddd", "vdda", "veld", "avdd", "vrefp", "vrefnp", "avdd_sar", "vdd_ac", "dvdd", "vdd_int", "vddac", "vdd_d"}
ignore_set = vss_set.union(vdd_set)#, clk_set)

class S3DET(object):
    def __init__(self, magicalDB, symTol=0.9):
        self.mDB = magicalDB
        self.dDB = magicalDB.designDB.db
        self.tDB = magicalDB.techDB
        self.symTol = symTol
        self.graph = nx.Graph()
        self.circuitNodes = dict()
        self.addPins = True
        self.constructGraph()
        self.graphSim = GraphSim.GraphSim(self.graph)
        #self.plotGraph()

    def systemSym(self, cktIdx, dirName):
        ckt = self.dDB.subCkt(cktIdx)
        cktNodes = range(ckt.numNodes())
        symVal = dict()
        symPair = dict()
        for nodeIdxA, nodeIdxB in combinations(cktNodes, 2):
            nodeA = ckt.node(nodeIdxA)
            nodeB = ckt.node(nodeIdxB)
            cktA = self.dDB.subCkt(nodeA.graphIdx)
            cktB = self.dDB.subCkt(nodeB.graphIdx)
            boxA = (cktA.gdsData().bbox().xLen(), cktA.gdsData().bbox().yLen())
            boxB = (cktB.gdsData().bbox().xLen(), cktB.gdsData().bbox().yLen())
            subgraphA = self.subgraph(cktIdx, nodeIdxA)
            subgraphB = self.subgraph(cktIdx, nodeIdxB)
            # Boundary box size check and circuit graph isomorphic check
            if boxA == boxB and nx.could_be_isomorphic(subgraphA, subgraphB):
                if nodeIdxA not in symVal:
                    symVal[nodeIdxA] = dict()
                symVal[nodeIdxA][nodeIdxB] = self.graphSim.specSimScore(subgraphA, subgraphB)
                print "Recognized symmetry pair:"
                print nodeA.name, nodeB.name, symVal[nodeIdxA][nodeIdxB]
        for idxA in symVal.keys():
            if idxA not in symVal:
                continue
            tempDict = symVal[idxA]
            tempList = list(tempDict.values())
            idxB = tempDict.keys()[tempList.index(max(tempList))]
            symPair[idxA] = idxB
            symVal.pop(idxB, None)
        #print symVal
        #print symPair
        hierGraph = self.hierGraph(cktIdx)
        selfSym = self.selfSym(symPair, hierGraph)
        symNet = self.symNet(cktIdx, symPair, selfSym)
        filename = dirName + ckt.name + ".sym"
        symFile = open(filename, "w")
        filename = dirName + ckt.name + ".symnet"
        netFile = open(filename, "w")
        for idxA in symPair:
            idxB = symPair[idxA]
            if symVal[idxA][idxB] >= self.symTol:
                nameA = ckt.node(idxA).name
                nameB = ckt.node(idxB).name
                symFile.write("%s %s\n" % (nameA, nameB))
        for idx in selfSym:
            name = ckt.node(idx).name
            symFile.write("%s\n" % name)
        for idxA in symNet:
            idxB = symNet[idxA]
            if idxA == idxB:
                name = ckt.net(idxA).name
                netFile.write("%s\n" % name)
            else:
                nameA = ckt.net(idxA).name
                nameB = ckt.net(idxB).name
                netFile.write("%s %s\n" % (nameA, nameB))
        symFile.close()
        netFile.close()

    def selfSym(self, symPair, hierGraph):
        selfSym = set()
        symVerified = set(symPair.keys()).union(symPair.values())
        for idxA in symPair.keys():
            idxB = symPair[idxA]
            if idxB:
                for comNei in set(nx.common_neighbors(hierGraph, idxA, idxB)).difference(symVerified):
                    selfSym.add(comNei)
        return selfSym

    def symNet(self, cktIdx, symPair, selfSym):
        ckt = self.dDB.subCkt(cktIdx)
        symNet = dict()
        netId = range(ckt.numNets())
        for netIdxA, netIdxB in combinations(netId, 2):
            devListA = self.devList(cktIdx, netIdxA) 
            devListB = self.devList(cktIdx, netIdxB) 
            sym = True
            for devA in devListA:
                if devA in symPair and symPair[devA] in devListB:
                    continue
                elif devA in selfSym and devA in devListB:
                    continue
                else:
                    sym = False
                    break
            if sym:
                symNet[netIdxA] = netIdxB
        #for netIdx in netId:
        #    devList = self.devList(cktIdx, netIdx)
        #    sym = True
        #    for devList
        return symNet


    def devList(self, cktIdx, netIdx):
        ckt = self.dDB.subCkt(cktIdx)
        devList = []
        for pinId in range(ckt.net(netIdx).numPins()):
            pinIdx = ckt.net(netIdx).pinIdx(pinId)
            pin = ckt.pin(pinIdx)
            devList.append(pin.nodeIdx)
        return devList


    def plotGraph(self, cktIdx=None, recursive=True):
        if cktIdx == None:
            labels = dict((n,d['name']) for n,d in self.graph.nodes(data=True))
            pos = nx.spring_layout(self.graph)
            nx.draw(self.graph, labels=labels, pos=pos)
            plt.show()
            if recursive:
                self.plotGraph(self.mDB.topCktIdx())
        else:
            ckt = self.dDB.subCkt(cktIdx)
            if magicalFlow.isImplTypeDevice(ckt.implType):
                return
            for nodes in range(ckt.numNodes()):
                subgraph = self.subgraph(cktIdx, nodes)
                labels = dict((n,d['name']) for n,d in subgraph.nodes(data=True))
                pos = nx.spring_layout(subgraph)
                if len(subgraph.nodes) > 4:
                    nx.draw(subgraph, labels=labels, pos=pos)
                    plt.show()
                if recursive:
                    self.plotGraph(ckt.node(nodes).graphIdx)

    def hierGraph(self, cktIdx):
        ckt = self.dDB.subCkt(cktIdx)
        hierGraph = nx.Graph()
        hierGraph.add_nodes_from(range(ckt.numNodes()))
        for netIdx in range(ckt.numNets()):
            net = ckt.net(netIdx)
            nodeList = set()
            if net.name in ignore_set:
                continue
            for pinId in range(net.numPins()):
                pinIdx = net.pinIdx(pinId)
                pin = ckt.pin(pinIdx)
                nodeList.add(pin.nodeIdx)
            for nodeA, nodeB in combinations(nodeList, 2):
                hierGraph.add_edge(nodeA, nodeB, index=netIdx)
        return hierGraph

    def subgraph(self, topIdx, nodeIdx):
        nodes = self.circuitNodes[topIdx][nodeIdx]
        subgraph = self.graph.subgraph(nodes)
        return subgraph

    def addNet(self, name):
        if name in ignore_set:
            self.graph.add_node(self.graph.number_of_nodes(), name=name, nodetype="pow")
        else:
            self.graph.add_node(self.graph.number_of_nodes(), name=name, nodetype="net")
        return self.graph.number_of_nodes() - 1

    def addInst(self, ckt, pinNum, ioNodeIdx):
        devNode = self.graph.number_of_nodes()
        nodeList = [devNode]
        self.graph.add_node(devNode, name=ckt.name, nodetype="dev")
        if self.addPins:
            assert pinNum <= ckt.numPins(), "Device type pin count not matched"
            for pinIdx in range(pinNum):
                self.graph.add_node(devNode+pinIdx+1, name=ckt.name+'_'+str(pinIdx), nodetype="pin")
                nodeList.append(devNode+pinIdx+1)
                self.graph.add_edge(devNode+pinIdx+1, devNode, edgetype="dev_pin")
                netNode = ioNodeIdx[pinIdx]
                self.graph.add_edge(devNode+pinIdx+1, netNode, edgetype="pin_net")
        else:
            for pinIdx in range(pinNum):
                netNode = ioNodeIdx[pinIdx]
                self.graph.add_edge(devNode, netNode, edgetype="dev_net")
        return nodeList
    
    def constructGraph(self):
        topCktIdx = self.mDB.topCktIdx()
        self.circuitNodes[topCktIdx] = dict()
        ckt = self.dDB.subCkt(topCktIdx)
        netNodeIdx = dict() # dict of net name to graph node idx
        for net in range(ckt.numNets()):
            netName = ckt.net(net).name
            nodeIdx = self.addNet(netName)
            netNodeIdx[net] = nodeIdx
        for nodeIdx in range(ckt.numNodes()):
            cktNode = ckt.node(nodeIdx)
            ioNodeIdx = dict()
            subCkt = self.dDB.subCkt(cktNode.graphIdx)
            cktType = subCkt.implType
            for pin in range(cktNode.numPins()):
                pinIdx = cktNode.pinIdx(pin)
                netIdx = ckt.pin(pinIdx).netIdx
                ioNodeIdx[pin] = netNodeIdx[netIdx]
            if not magicalFlow.isImplTypeDevice(cktType):
                subNodes = self.constructSubgraph(cktNode.graphIdx, ioNodeIdx)
            elif cktType in [magicalFlow.ImplTypePCELL_Nch, magicalFlow.ImplTypePCELL_Pch]:
                subNodes = self.addInst(subCkt, 3, ioNodeIdx)
            elif cktType in [magicalFlow.ImplTypePCELL_Res, magicalFlow.ImplTypePCELL_Cap]:
                subNodes = self.addInst(subCkt, 2, ioNodeIdx)
            else:
                raise Exception('Device type of %s not supported' % subCkt.name)
            self.circuitNodes[topCktIdx][nodeIdx] = subNodes
        self.removeNetNodes()

    def constructSubgraph(self, cktIdx, topIoNodeIdx):
        ckt = self.dDB.subCkt(cktIdx)
        self.circuitNodes[cktIdx] = dict()
        netNodeIdx = dict()
        nodeList = []
        for net in range(ckt.numNets()):
            if ckt.net(net).isIo():
                netNodeIdx[net] = topIoNodeIdx[ckt.net(net).ioPos]
            else:
                netName = ckt.net(net).name
                netIdx = self.addNet(netName)
                netNodeIdx[net] = netIdx
        for nodeIdx in range(ckt.numNodes()):
            cktNode = ckt.node(nodeIdx)
            subCkt = self.dDB.subCkt(cktNode.graphIdx)
            cktType = subCkt.implType
            ioNodeIdx = dict()
            for pin in range(cktNode.numPins()):
                pinIdx = cktNode.pinIdx(pin)
                netIdx = ckt.pin(pinIdx).netIdx
                ioNodeIdx[pin] = netNodeIdx[netIdx]
            if not magicalFlow.isImplTypeDevice(cktType):
                subNodes = self.constructSubgraph(cktNode.graphIdx, ioNodeIdx)
            elif cktType in [magicalFlow.ImplTypePCELL_Nch, magicalFlow.ImplTypePCELL_Pch]:
                subNodes = self.addInst(subCkt, 3, ioNodeIdx)
            elif cktType in [magicalFlow.ImplTypePCELL_Res, magicalFlow.ImplTypePCELL_Cap]:
                subNodes = self.addInst(subCkt, 2, ioNodeIdx)
            else:
                raise Exception('Device type of %s not supported' % subCkt.name)
            self.circuitNodes[cktIdx][nodeIdx] = subNodes
            nodeList.extend(subNodes)
        return nodeList
    
    def removeNetNodes(self):
        removeNode = []
        for node in self.graph:
            if self.graph.nodes[node]['nodetype'] is 'pow':
                removeNode.append(node)
            elif self.graph.nodes[node]['nodetype'] is 'net':
                for pinA, pinB in combinations(self.graph[node], 2):
                    self.graph.add_edge(pinA, pinB, edgetype="pin_pin")
                removeNode.append(node)
        self.graph.remove_nodes_from(removeNode)

