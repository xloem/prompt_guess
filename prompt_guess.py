
# pattern for prompts of arbitrary length

# - when input comes in, it is categorised in a decision tree to decide what prompt can best produce the right output for it
# - the categorisation is done with prompts: so each node in the tree has a categorisation prompt, and two children

# decision tree internode:
#   - categorisation prompt
#   - children
# decision tree leaf:
#   - input-output prompt

# so, we start as a leaf, and once things are difficult we make nodes to manage them.

import tensors

class Prompts:
    class Node:
        def __init__(self, ctx, entry_ids_pairs = [], *child_nodes):
            self.ctx = ctx
            self.entry_ids_pairs = entry_ids_pairs
            self.child_nodes = child_nodes
            self.max_entry_tokens = self.ctx.extra_tokens_per_entry * 4
            for input_ids, output_ids in entry_ids_pairs:
                self.add_entry_ids(input_ids, output_ids)
        def guess(self, input, auto_add = False):
            try:
                prompt_ids = self.get_prompt_ids(input)
                if len(prompt_ids) >= self.ctx.max_tokens:
                    raise OverflowError
                output_ids = self.ctx.generate_ids(
                    prompt_ids,
                    self.max_entry_tokens * 2
                )
                output = self.ctx.detokenize(output_ids)
                if output.startswith(self.ctx.output_prefix_extra):
                    output = output[len(self.ctx.output_prefix_extra):]
                if auto_add:
                    self.add(input, output)
                return output
            except OverflowError:
                if len(self.entry_ids_pairs) < 4:
                    raise RuntimeError('not enough examples')
                # too much data.  let's split it.
                self.break_prompt()
                return self.guess(input, auto_add)
        def add(self, input, output):
            self.add_entry_ids(
                self.ctx.tokenize_input(input),
                self.ctx.tokenize_output(output)
            )
        def add_entry_ids(self, input_ids, output_ids):
            if len(input_ids) + len(output_ids) > self.max_entry_tokens:
                self.max_entry_tokens = len(input_ids) + len(output_ids)
            self.entry_ids_pairs.append((input_ids, output_ids))
        def get_prompt_ids(self, input = None):
            input_ids = self.ctx.tokenize_input(input) if input is not None else None
            return self.ctx.get_prompting_ids(self.entry_ids_pairs, input_ids)
        def get_prompt(self, input = None):
            result = self.ctx.detokenize(self.get_prompt_ids(input))
            if input is None:
                result += self.ctx.input_prefix_extra
            return result
        def break_prompt(self, num_groups = 2):
            raise AssertionError('prompt too long')
            #if len(self.child_nodes):
            #    raise AssertionError('already broken into groups')
            #if num_groups < 2:
            #    raise AssertionError('must have at least 2 groups to break entries')
            ## 1. break the entries of the leaf into random groups
            #from random import shuffle
            #random_entries= [*self.entry_ids_pairs]
            #shuffle(random_entries)

            #proposed_groups = []
            #last_idx = 0
            #for group_id in range(num_groups):
            #    next_idx = len(random_entries) * group_id // (num_groups - 1)
            #    proposed_groups.append(random_entries[last_idx:next_idx])
            #    last_idx = next_idx

            ## 2. for each entry, see which group can predict it
            ##    migrate entries to working groups until they are all sorted
            #            # if both can predict it, add it to a third group, and retry later
            #unsorted_predictable = []
            #unsorted_unpredictable = []
            #for entry in random_entries:
            #    entry_group_id = None
            #    input_ids, output_ids = entry
            #    predicts = []
            #    for group_id, group in enumerate(proposed_groups):
            #        filtered_group = list(group)
            #        try:
            #            filtered_group.remove(entry)
            #            entry_group_id = group_id
            #        except:
            #            pass
            #        prompt_ids = self.ctx.get_prompting_ids(filtered_group, filtered_group, input_ids)
            #        guessed_ids = self.ctx.generate_ids(prompt_ids, len(output_ids))
            #        if guessed_ids == output_ids:
            #            predicts.append(group_id)
            #    if len(predicts) < 1:
            #        unsorted_unpredictable.append(entry)
            #    elif len(predicts) > 1:
            #        unsorted_predictable.append(entry)
            #    else:
            #        group_id = predicts[0]
            #        group = proposed_groups[group_id]
            #        if group_id != entry_group_id:
            #            

            ## to compare the entries, we'll want to separate the input and the output ids from each other
    def __init__(self, pipeline, input_prefix = 'IN: ', input_postfix = '\n', output_prefix = 'OUT: ', output_postfix = '\n'):
        self.pipeline = pipeline
        self.input_prefix_extra = ''
        while input_prefix.endswith(' '):
            input_prefix = input_prefix[:-1]
            self.input_prefix_extra += ' '
        self.output_prefix_extra = ''
        while output_prefix.endswith(' '):
            output_prefix = output_prefix[:-1]
            self.output_prefix_extra += ' '
        self.input_prefix_ids = self.tokenize(input_prefix)
        self.input_postfix_ids = self.tokenize(input_postfix)
        self.output_prefix_ids = self.tokenize(output_prefix)
        self.output_postfix_ids = self.tokenize(output_postfix)
        self.tensors = tensors.get_backend(self.input_prefix_ids)
        self.allowed_token_ids = self.tensors.arange(self.pipeline.tokenizer.vocab_size)
        self.root = Prompts.Node(self, [])
    def guess(self, input, auto_add = False):
        return self.root.guess(input, auto_add)
    def add(self, input, output):
        return self.root.add(input, output)
    def get_prompt(self, input = None):
        return self.root.get_prompt(input)
    @property
    def input_prefix(self):
        return self.detokenize(self.input_prefix_ids) + self.input_prefix_extra
    @property
    def input_postfix(self):
        return self.detokenize(self.input_postfix_ids)
    @property
    def output_prefix(self):
        return self.detokenize(self.output_prefix_ids) + self.output_prefix_extra
    @property
    def output_postfix(self):
        return self.detokenize(self.output_postfix_ids)
    @property
    def max_tokens(self):
        try:
            return self.pipeline.model.config.max_position_embeddings
        except:
            return self.pipeline.model.config.n_positions
    @property
    def extra_tokens_per_entry(self):
        return len(self.input_prefix_ids) + len(self.input_postfix_ids) + len(self.output_prefix_ids) + len(self.output_postfix_ids)
    def get_prompting_ids(self, entry_ids_pairs, input_ids = None):
        return self.tensors.concat((
            *(
                ids
                for input_ids, output_ids in entry_ids_pairs
                for ids in (
                    self.input_prefix_ids, input_ids, self.input_postfix_ids,
                    self.output_prefix_ids, output_ids, self.output_postfix_ids
                )
            ),
            *(
                (self.input_prefix_ids, input_ids, self.input_postfix_ids,
                 self.output_prefix_ids)
                    if input_ids is not None
                    else (self.input_prefix_ids,)
            )
        ))
    def tokenize_input(self, input):
        return self.tokenize(self.input_prefix_extra + input)
    def tokenize_output(self, output):
        return self.tokenize(self.output_prefix_extra + output)
    def detokenize_input(self, input):
        result = self.detokenize(input)
        if result.startswith(self.input_prefix_extra):
            return result[len(self.input_prefix_extra):]
        else:
            return result
    def detokenize_output(self, output):
        result = self.detokenize(output)
        if result.startswith(self.output_prefix_extra):
            return result[len(self.output_prefix_extra):]
        else:
            return result
    def tokenize(self, input):
        return self.pipeline.tokenizer.encode(input, return_tensors = self.pipeline.framework)[0]
    def detokenize(self, token_ids):
        return self.pipeline.tokenizer.decode(token_ids)
    def generate_ids(self, input_ids, max_output_tokens):
        try:
            self.pipeline.model.generate(
                self.tensors.stack((input_ids,), axis=0),
                max_length = min(self.max_tokens, len(input_ids) + max_output_tokens + self.extra_tokens_per_entry),
                top_p = 0.0001,
                temperature = 0.10001,
                #do_sample = False,
                return_full_text = False,
                prefix_allowed_tokens_fn = self._raise_terminate_seq
            )[0]
            # if the termination sequence isn't found within max_tokens, then it would be an overflow once it is finally generated
            raise OverflowError
        except Prompts._TerminationSequenceFound as seq_exc:
            return seq_exc.args[0]
    def _raise_terminate_seq(self, batch_id, gen_ids):
        terminate = False
        try:
            if (gen_ids[-len(self.input_prefix_ids):] == self.input_prefix_ids).all():
                len_sum = len(self.input_prefix_ids) + len(self.output_postfix_ids)
                if (gen_ids[-len_sum:-len(self.input_prefix_ids)] == self.output_postfix_ids).all():
                    terminate = True
        except AttributeError:
            if [*gen_ids[-len(self.input_prefix_ids):]] == [*self.input_prefix_ids]:
                len_sum = len(self.input_prefix_ids) + len(self.output_postfix_ids)
                if [*gen_ids[-len_sum:-len(self.input_prefix_ids)]] == [*self.output_postfix_ids]:
                    terminate = True
        if terminate:
            result = gen_ids[:-len_sum]
            raise Prompts._TerminationSequenceFound(result)
        return self.allowed_token_ids
    class _TerminationSequenceFound(StopIteration):
        pass
