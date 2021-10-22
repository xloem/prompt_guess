### DRAFT DRAFT DRAFT

import collections, random

# utility for specific successful results is held as a tuple of (portion_demonstrated, total_possible)

class Usefulness:
    def __init__(self, *summarize_together):
        self._utility_ratios = collections.defaultdict(lambda: (0,0))
        for subuseful in summarize_together:
            for result, utility_ratio in subuseful.utility_priority_map.items():
                if utility_ratio[1]:
                    demonstrated, possible = self._utilities[result]
                    demonstrated += Usefulness.ratio_to_utility(utility)
                    possible += 1
                    self._utilities[result] = (demonstrated, possible)
    @property
    def utility(self):
        return self.utility_for(*self._utilities.values())
    def utility_for(self, *result_classes):
        utility_ratios = [self._utility_ratios[result_class] for result_class in result_classes]
        utilities = (
            Usefulness.ratio_to_utility(utility_ratio)
            for utility_ratio in utility_ratios
        )
        return sum(utilities) / len(result_classes)
    @property
    def utility_priority_map(self):
        utilities = [
            (Usefulness.ratio_to_utility(utility_ratio), result)
            for result, utility_ratio in self._utility_ratios.items()
        ]
        utilities.sort(reverse = True)
        return {
            result : utility
            for utility, result in utilities
        }
    @staticmethod
    def ratio_to_utility(demonstrated, possible):
        if possible == 0:
            return 0.5
        else:
            return demonstrated / possible
    def add(self, contribution : float, result_class : hash, success : bool):
        '''
        contribution: degree to which this participated in the result
        result: class of the result; utility is averaged fairly across these
        success: False if this was a failure
        '''
        demonstrated, possible = self._utility_ratios[result_class]
        possible += contribution
        if success:
            demonstrated += contribution
        elif demonstrated == 0:
            # there might be bug here.  the heuristic doesn't sustain trying things in new situations that are separated into result classes.
            # it might would be better to add a smaller fraction of contribution for every failure, or to track untried scenarios maybe via more classes
            demonstrated += contribution / 2
        self._utility_ratios[result_class] = (demonstrated, possible)

class OrderedEntry:
    def __init__(self):
        self.inclusion_usefulness = Usefulness()
        self._after_usefulness = defaultdict(Usefulness)
    def add(self, result_class : hash, list_of_entries : iter, this_idx : int, success : bool):
        if list_of_entries[this_idx] is not self:
            raise AssertionError('incorrect this_idx')
        inclusion_contribution = 1.0 / len(list_of_entries)
        self.inclusion_usefulness.add(inclusion_contribution, result_class, success)

        if len(list_of_entries) > 1:
            order_contribution = 1.0 / (len(list_of_entries) - 1)
            for other_item in list_of_entries:
                if other_item is self:
                    # terminate loop to only consider items this item came after
                    break
                else:
                    after_usefulness = self._after_usefulness[other_item]
                    after_usefulness.add(order_contribution, result_class, success)
    def order_usefulness(self, list_of_entries : iter, this_idx : int):
        if list_of_entries[this_idx] is not self:
            raise AssertionError('incorrect this_idx')
        return Usefulness(
            self.inclusion_contribution,
            *(
                self._after_usefulness[item]
                for item in list_of_entries[:this_idx]
            ),
            *(
                item._after_usefulness[self]
                for item in list_of_entries[this_idx + 1:]
            )
        )
    @staticmethod
    def order(self, possible_entries, result_classes, overflow_predicate = None, success_predicate = None, sample = False):
        if type(possible_entries) is not set:
            possible_entries = set(possible_entries)
        # find highly useful choices and combine them

        # a choice is inclusion of an item, ordering an item after another,
        # or noninclusion of an item

                # maybe finding good ordering choices would be really helpful
                # we could put inclusion adjacent to them if no good orderings are known

        # utility, item before, item after
        best_ordering_choices = []
        all_items = defaultdict(lambda: 0)
        total_utility = 0

        def consider_choice(utility, before_entry, after_entry = None):
            if sample or (len(best_ordering_choices) == 0 or utility > best_ordering_choices[-1][0]):
                best_ordering_choices.append((utility, before_entry, after_entry))
                if sample:
                    total_utility += utility
                else:
                    all_items[before_entry] += 1
                    if after_entry is not None:
                        all_items[after_entry] += 1
                    best_ordering_choices.sort(reverse=True)
                    if overflow_predicate is not None:
                        while overflow_predicate(all_items.keys()):
                            popped_utility, popped_before, popped_after = best_ordering_choices.pop()
                            all_items[popped_before] -= 1
                            if popped_after is not None:
                                all_items[popped_after] -= 1

        for after_entry in possible_entries:
            #for before_entry, usefulness in after_entry._after_usefulnesses.items():
            #    if before_entry in possible_entries:
            #        utility = usefulness.utility_for(result_classes)
            #        consider_choice(utility, before_entry, after_entry)
            for before_entry in possible_entries:
                usefulness = after_entry._after_usefulnesses[before_entry]
                utility = usefulness.utility_for(result_classes)
                consider_choice(utility, before_entry, after_entry)

            utility = after_entry.inclusion_usefulness.utility_for(result_classes)
            consider_choice(utility, after_entry)

        # now we have a set of best choices that fit within the overflow, ordered according to quality
        # basically, we can run down them until the solution is met

        # is this algorithm correct?
        # we'll store, for each item, a list of items before, and a list of items after
            # we can even store, for each item, just a list of items before
        items_before = defaultdict(set)
        items_after = defaultdict(set)
        ordered_items = set()
        unordered_items = set()

        ordered_list = []
        proposal = None

        def form_proposal():
            # todo: this could probably be made correct by recursively walking options
            sort(ordered_list, key=lambda item: len(items_after[item]))
            proposal = list(ordered_list)
            for item in unordered_items:
                proposal.insert(random.randint(0, len(unordered_items)+1), item)
            return proposal

        def choices_sample(best_ordering_choices, total_utility):
            while len(best_ordering_choices):
                item_num = random.random() * total_utility   
                cur_num = 0
                for idx, choice in enumerate(best_ordering_choices):
                    cur_num += choice[0]
                    if cur_num >= item_num:
                        break
                yield choice
                total_utility -= chioce[0]
                del best_ordering_choices[idx]

        if sample:
            best_ordering_choices = choices_sample(best_ordering_choices, total_utility)

        for utility, before_entry, after_entry in best_ordering_choices:
            if after_entry is not None:
                if after_entry not in items_before[before_entry]:
                    unordered_items.difference_update((before_entry, after_entry))
                    ordered_items.update((before_entry, after_entry))
                    items_after[before_entry].add(after_entry)
                    items_before[after_entry].add(before_entry)
                else:
                    continue # ordering conflicts are skipped since this is just a heuristic
                             # in this case, the higher-priority choice was already included
            else:
                unordered_items.add(before_entry)

            # now we can form a list with the ordering and see if it succeeds 
            if success_predicate is not None:
                proposal = form_ordered_list()
                if success_predicate(proposal):
                    return proposal
        if proposal is None:
            proposal = form_ordered_list()
        return proposal







