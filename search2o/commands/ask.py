# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://search2o.com/legal/license.txt.

from pydantic import JsonValue, ValidationError

from search2o.common.enums import AgentWords, TraceType
from search2o.common.exceptions import ShowMessage
from search2o.common.jsonvalidation import JsonValidator
from search2o.common.typechecker import ExpectedType
from search2o.execution.agent_executor import AgentExecutor, CommandExec, AskException, CommandInvocation
from search2o.execution.statenodes import AskCommandNode
from search2o.models.schemaobjects import AskInputModel, AskInputsModel, CommandName


class AskCommand(CommandExec):
    async def exec_command(self, inv: CommandInvocation, executor: AgentExecutor) -> JsonValue:
        function, command, command_ns, replay_index = inv.frame, inv.command, inv.command_ns, inv.replay_index
        node = executor.get_node(replay_index, AskCommandNode)
        ask_inputs: list[dict] | None = executor.param(function, command, command_ns, AgentWords.inputs, ExpectedType.listt)
        message: str = executor.param(function, command, command_ns, AgentWords.message, ExpectedType.strt)

        new_list: list[AskInputModel] = []
        for item in ask_inputs:
            try:
                ai = AskInputModel.model_validate(item)
                new_list.append(ai)
            except ValidationError as e:
                raise ShowMessage(f"Error in inputs in the {CommandName.ask} command: {JsonValidator.format_validation_error(e)}")

        inputs = AskInputsModel(inputs=new_list, message=message)
        if node:
            answers = executor.ask_answers if executor.ask_answers else {}
            missing = [ai.name for ai in new_list if not ai.hidden and ai.name not in answers]
            if missing:
                executor.stream_iter.trace(lambda: f"The user did not answer {missing}, so the agent is asking again",
                                           TraceType.input, inv.path)
                raise AskException(node=AskCommandNode(), ask_input=inputs)
            given = {ai.name: answers[ai.name] for ai in new_list if ai.name in answers}
            executor.stream_iter.trace(lambda: f"The user answered: {given}", TraceType.output, inv.path)
            return given

        executor.stream_iter.trace(lambda: f"Asking the user for {[ai.name for ai in new_list]} "
                                           f"with the message {message!r}", TraceType.input, inv.path)
        raise AskException(node=AskCommandNode(), ask_input=inputs)

