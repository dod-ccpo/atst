import os
import sys

parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(parent_dir)

from atat.domain.csp.cloud.models import BillingInstructionCSPPayload
from script.provision.provision_base import handle


def report_clin(csp, inputs):
    billing_instruction = BillingInstructionCSPPayload(
        **{**inputs.get("initial_inputs"), **inputs.get("csp_data")}
    )
    result = csp.create_billing_instruction(billing_instruction)
    if result.get("status") == "ok":
        return result.get("body").dict()
    else:
        print("there was an error during the request:")
        print(result.get("body"))


def report_clins(csp, inputs):
    clins_to_report = inputs.get("new_clins", [])
    initial_inputs = inputs["initial_inputs"]
    initial_clin_data = {
        "initial_clin_amount": initial_inputs["initial_clin_amount"],
        "initial_clin_start_date": initial_inputs["initial_clin_start_date"],
        "initial_clin_end_date": initial_inputs["initial_clin_end_date"],
        "initial_clin_type": initial_inputs["initial_clin_type"],
        "initial_task_order_id": initial_inputs["initial_task_order_id"],
    }
    reported_clins = []
    for clin in clins_to_report:
        initial_inputs.update(
            {
                "initial_clin_amount": clin["amount"],
                "initial_clin_start_date": clin["start_date"],
                "initial_clin_end_date": clin["end_date"],
                "initial_clin_type": clin["type"],
                "initial_task_order_id": clin["task_order_id"],
            }
        )
        reported_clin = report_clin(csp, inputs)
        if reported_clin:
            reported_clins.append(reported_clin.get("reported_clin_name"))

    # Reset initial clin
    initial_inputs.update(initial_clin_data)

    return dict(reported_clins=reported_clins)


if __name__ == "__main__":
    handle(report_clins)
