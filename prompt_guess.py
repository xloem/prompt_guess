
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
    class Leaf:
        def __init__(self, ctx, entries_ids = []):
            self.ctx = ctx
            self.entries_ids = []
            self.max_entry_tokens = self.ctx.extra_tokens_per_entry * 4
            for entry_ids in entries_ids:
                self.add_entry_ids(entry_ids)
        def guess(self, input, auto_add = False):
            try:
                prompt_ids = self.get_prompt_ids(input)
                if len(prompt_ids) >= self.ctx.max_tokens:
                    raise OverflowError
                output_ids = self.ctx.generate_ids(prompt_ids, 2048)#self.max_entry_tokens * 2)
                output = self.ctx.detokenize(output_ids)
                if output.startswith(self.ctx.output_prefix_extra):
                    output = output[len(self.ctx.output_prefix_extra):]
                if auto_add:
                    self.add(input, output)
                return output
            except OverflowError:
                if len(self.entries_ids) < 4:
                    raise RuntimeError('not enough examples')
                # too much data.  let's split it.
                raise OverflowError(self, input)
        def add(self, input, output):
            self.entries_ids.append(self.ctx.entry_ids(input, output))
        def add_entry_ids(self, entry_ids):
            if len(entry_ids) > self.max_entry_tokens:
                self.max_entry_tokens = len(entry_ids)
            self.entries_ids.append(entry_ids)
        def get_prompt_ids(self, input):
            return self.ctx.tensors.concat((
                *self.entries_ids,
                self.ctx.prompting_ids(self.ctx.input_prefix_extra + input)
            ))
        def get_prompt(self, input):
            return self.ctx.detokenize(self.get_prompt_ids(input))
            
    class Node:
        def __init__(self):
            pass
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
        self.root = Prompts.Leaf(self, [])
    def guess(self, input, auto_add = False):
        return self.root.guess(input, auto_add)
    def add(self, input, output):
        return self.root.add(input, output)
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
    def prompting_ids(self, input):
        return self.tensors.concat((
            self.input_prefix_ids, self.tokenize(input), self.input_postfix_ids,
            self.output_prefix_ids
        ))
    def entry_ids(self, input, output):
        return self.tensors.concat((
            self.input_prefix_ids, self.tokenize(self.input_prefix_extra + input), self.input_postfix_ids,
            self.output_prefix_ids, self.tokenize(self.output_prefix_extra + output), self.output_postfix_ids
        ))
    def tokenize(self, input):
        return self.pipeline.tokenizer.encode(input, return_tensors = self.pipeline.framework)[0]
    def detokenize(self, token_ids):
        return self.pipeline.tokenizer.decode(token_ids)
    def generate_ids(self, input_ids, max_new_tokens):
        try:
            self.pipeline.model.generate(
                self.tensors.stack((input_ids,), axis=0),
                max_length = min(self.max_tokens, len(input_ids) + max_new_tokens),
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
