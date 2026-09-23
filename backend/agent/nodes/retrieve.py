from agent.tools import dossier_tools


def load_structure(state):
    return {"dossier_structure": dossier_tools.get_dossier_structure()}
