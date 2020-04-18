"""Astar search."""
from abc import ABC, abstractmethod
from queue import PriorityQueue
from typing import Callable, List

from multi_sokoban import actions

import sys

count = 0


def default_heuristic(a, b):
    """Apply simple heuristic."""
    (x1, y1) = a
    (x2, y2) = b
    return abs(x1 - x2) + abs(y1 - y2)


class BestFirstSearch(ABC):
    """Abstract class for BFS."""

    def __init__(
        self, init_state: actions.StateInit, heuristic: Callable = default_heuristic,
    ):
        """Initialize strategy."""
        self.frontier = PriorityQueue()
        self.heuristic = heuristic
        self.leaf = init_state
        self.count = 0
        self.calc_heuristic_for(self.leaf)

    @abstractmethod
    def get_and_remove_leaf(self):
        """Depend on the heuristic method."""
        raise NotImplementedError

    '''
        #try and use maps instead of for loops!!

        def stateMethod(state, goalKey):

        def keyMethod(key):

        def posMethod1(a):
        
        def posMethod2(a):

        def agentMethod1(state, agentKey, boxPos, goalPos):
    '''

    def calc_heuristic_for(self, states: List[actions.StateInit]):
        """Calculate heuristic for states in place."""
        if type(states) is not list:
            states = [states]
        if len(states) == 0:
            return None

        goalKeys = states[0].getGoalKeys()

        for state in states:
            boxGoalCost = 0
            agtBoxCost = 0
            agtBoxCosts = []
            
            for key in goalKeys:
                goalParams = state.getGoalsByKey(key)
                boxParams = state.getBoxesByKey(key)

                # find every position of goals and boxes with the given key
                for goalPos, goalColor in goalParams:
                    for boxPos, _ in boxParams:
                        # only take agents with the same color as goalColor
                        agentKeys = state.getAgentsByColor(goalColor)
                        for agentKey in agentKeys:
                            agentPos = state.getAgentsByKey(agentKey)[0][0]
                            boxGoalCost += default_heuristic(boxPos, goalPos)
                            #agtBoxCost += default_heuristic(agentPos, boxPos)
                            agtBoxCosts.append(default_heuristic(agentPos, boxPos))
                            # print(goalPos, boxPos, goalColor, agentPos, agentKey)
                #print(agtBoxCost, file=sys.stderr, flush=True)
            agtBoxCost = min(agtBoxCosts)
            state.h = boxGoalCost + agtBoxCost
            state.f = state.g + state.h
            #state.updateParentCost(total_cost)


            
    def walk_best_path(self):
        """Return the solution."""
        return self.leaf.bestPath()

    def frontier_empty(self):
        """Return if solution couldn't be solved."""
        return self.frontier.empty()


class aStarSearch(BestFirstSearch):
    """BFS with A*."""

    def get_and_remove_leaf(self):
        """Apply the heuristic and update the frontier."""
        explored_states = self.leaf.explore()
        self.calc_heuristic_for(explored_states)

        for state in explored_states:
            self.count += 1
            self.frontier.put((state.f, self.count, state))
        self.leaf = self.frontier.get()[2]

    def __str__(self):
        """Printable descriptuion."""
        return "A* Best First Search"


def aStarSearch_func(initState):
    """Functional legacy approach."""
    global count
    # count = 0 should be static and only initialized in the start,
    # it's needed for unique hashes
    frontier = PriorityQueue()
    leaf = initState
    calcHuristicsFor(leaf)

    while not leaf.isGoalState():
        exploredStates = leaf.explore()
        calcHuristicsFor(exploredStates)

        for state in exploredStates:
            count += 1
            frontier.put((state.h, count, state))
            
        leaf = frontier.get()[2]

    return leaf.bestPath(), leaf


def calcHuristicsFor(states):
    """Functional legacy approach."""
    """Calculate heuristic for states in place."""
    if type(states) is not list:
        states = [states]
    if len(states) == 0:
        return None

    goalKeys = states[0].getGoalKeys()

    for state in states:
        boxGoalCost = 0
        agtBoxCost = 0
        agtBoxCosts = []
        
        for key in goalKeys:
            goalParams = state.getGoalsByKey(key)
            boxParams = state.getBoxesByKey(key)

            # find every position of goals and boxes with the given key
            for goalPos, goalColor in goalParams:
                for boxPos, _ in boxParams:
                    # only take agents with the same color as goalColor
                    agentKeys = state.getAgentsByColor(goalColor)
                    for agentKey in agentKeys:
                        agentPos = state.getAgentsByKey(agentKey)[0][0]
                        boxGoalCost += default_heuristic(boxPos, goalPos)
                        agtBoxCosts.append(default_heuristic(agentPos, boxPos))
                        # print(goalPos, boxPos, goalColor, agentPos, agentKey)
            #print(agtBoxCost, file=sys.stderr, flush=True)
        agtBoxCost = min(agtBoxCosts)
        state.h = boxGoalCost + agtBoxCost
        state.f = state.g + state.h
        #state.updateParentCost(total_cost)

