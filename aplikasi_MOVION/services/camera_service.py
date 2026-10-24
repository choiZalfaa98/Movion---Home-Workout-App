from pygrabber.dshow_graph import FilterGraph

# --- GETTING REGISTERED CAMERAS FROM THE DEVICE SYSTEM ---
def get_cameras():
    graph = FilterGraph()

    cameras = graph.get_input_devices()

    return [
        {
            "name": name,
            "index": i
        }
        for i, name in enumerate(cameras)
    ]
