# Copyright (c) 2025-present Search2o, Inc.
# All rights reserved. Proprietary software.
# Running or operating this software requires valid, ongoing authorization from Search2o.
# See the LICENSE.md file and https://tactet.com/legal/license.html.

from pydantic import JsonValue, ValidationError

from tactet.common.enums import AgentWords, TraceType
from tactet.common.exceptions import ShowMessage
from tactet.common.jsonvalidation import JsonValidator
from tactet.common.typechecker import ExpectedType
from tactet.execution.agent_executor import AgentExecutor, CommandExec, AskException, CommandInvocation
from tactet.execution.statenodes import AskCommandNode
from tactet.models.apimodels import ASK_KEY
from tactet.models.schemaobjects import AskInputModel, AskInputsModel, CommandName


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
                raise ShowMessage(f"Error in inputs in the {CommandName.ask} command: {JsonValidator.error_text(e, item)}")

        inputs = AskInputsModel(inputs=new_list, message=message)
        if node:
            scope = executor.ask_answers
            answers = scope.get(ASK_KEY) if isinstance(scope, dict) else None
            answers = answers if isinstance(answers, dict) else {}
            missing = [ai.name for ai in new_list if not ai.hidden and ai.name not in answers]
            if missing:
                executor.stream_iter.trace(lambda: f"The user did not answer {missing}, so the agent is asking again",
                                           TraceType.input, inv.path)
                raise AskException(node=AskCommandNode(), ask_input={ASK_KEY: inputs})
            given = {ai.name: answers[ai.name] for ai in new_list if ai.name in answers}
            executor.stream_iter.trace(lambda: f"The user answered: {given}", TraceType.output, inv.path)
            return given

        executor.stream_iter.trace(lambda: f"Asking the user for {[ai.name for ai in new_list]} "
                                           f"with the message {message!r}", TraceType.input, inv.path)
        raise AskException(node=AskCommandNode(), ask_input={ASK_KEY: inputs})

