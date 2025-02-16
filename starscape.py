import bpy
import sys
import math
import random
import mathutils

### Helper function ########################################################################

def create_or_reuse_mesh_object(name):
    # Load/create the mesh
    try:
        mesh = bpy.data.meshes[name + "_mesh"]
        mesh.clear_geometry()
    except KeyError:
        mesh = bpy.data.meshes.new(name + "_mesh")
    # Load/create the object
    try:
        obj = bpy.data.objects[name]
    except KeyError:
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
    return obj

def random_spherical_coordinates():
    phi = random.random() * 2 * math.pi
    theta = math.asin(2 * random.random() - 1)
    return phi, theta

def spherical_to_cartesian_coordinates(radius, phi, theta):
    x = radius * math.cos(phi) * math.cos(theta)
    y = radius * math.sin(phi) * math.cos(theta)
    z = radius * math.sin(theta)
    return x, y, z

def hide_node_outputs(node):
    for socket in node.outputs:
        if not socket.is_linked:
            socket.hide = True

def make_node(nodes, node_type, x, y):
    node = nodes.new(node_type)
    node.location = (x, y)
    return node

def make_group_node(nodes, group, x, y):
    node = nodes.new("ShaderNodeGroup")
    node.node_tree = group
    node.location = (x, y)
    return node

def make_math_node(nodes, function, x, y, default_1 = 0.5, default_2 = 0.5):
    node = nodes.new("ShaderNodeMath")
    node.operation = function
    node.location = (x, y)
    node.inputs[0].default_value = default_1
    node.inputs[1].default_value = default_2
    return node

def connect_nodes(tree, *args):
    if len(args) < 4 or (len(args) - 4) % 3 != 0:
        raise Exception("Invalid number of arguments!")

    # Make n links
    n = (len(args) - 1) // 3
    for i in range(n):
        node_a = args[3 * i]
        node_b = args[3 * (i + 1)]
        output = args[3 * i + 1]
        input = args[3 * i + 2]
        tree.links.new(node_b.inputs[input], node_a.outputs[output])

def make_group_inputs(group, x, y, *sockets):
    if len(sockets) % 2 != 0:
        raise Exception("Invalid number of arguments!")
    node = group.nodes.new("NodeGroupInput")
    node.location = (x, y)

    for i in range(len(sockets) // 2):
        group.interface.new_socket(sockets[2 * i + 1], in_out='INPUT', socket_type="NodeSocket" + sockets[2 * i])

    return node

def make_group_outputs(group, x, y, *sockets):
    if len(sockets) % 2 != 0:
        raise Exception("Invalid number of arguments!")
    node = group.nodes.new("NodeGroupOutput")
    node.location = (x, y)
    
    for i in range(len(sockets) // 2):
        group.interface.new_socket(sockets[2 * i + 1], in_out='OUTPUT', socket_type="NodeSocket" + sockets[2 * i])

    return node

### Main function ##########################################################################

def generate_starscape(props):
    # Get the scene camera
    camera = bpy.context.scene.camera
    if not camera or camera.data.type != "PERSP":
        return False

    # Initialize random number generator
    random.seed(props.random_seed)

    # Create stars positions (mesh data consisting only of vertices, radius = 1)
    vertices = []
    N = 1000 * props.star_density
    if props.hemisphere:
        N = N / 2
    for i in range(round(N)):
        # Generate a random location at random across the sky
        phi, theta = random_spherical_coordinates()
        x, y, z = spherical_to_cartesian_coordinates(1, phi, theta)
        if props.hemisphere:
            z = abs(z)
        vertices.append((x, y, z))

    # Load/create the star location mesh
    stars_obj = create_or_reuse_mesh_object("Starscape")
    # Set the mesh to the star data
    stars_obj.data.from_pydata(vertices, [], [])

    # Add a star template
    # Usa a triangle, because it uses the least amount of vertices and faces
    vertices = []
    s = 0.0002
    q = s * math.sqrt(3)
    vertices.append((+0, 0, +2 * s))
    vertices.append((-q, 0, -1 * s))
    vertices.append((+q, 0, -1 * s))
    template_obj = create_or_reuse_mesh_object("Star_Template")
    template_obj.data.from_pydata(vertices, [(0, 1), (0, 2), (1, 2)], [(0, 1, 2)])

    ### Material ###########################################################################

    # Create the new material "Star Shader"
    try:
        shader = bpy.data.materials["Star Shader"]
    except KeyError:
        shader = bpy.data.materials.new("Star Shader")

    # Use nodes
    shader.use_nodes = True
    node_tree = shader.node_tree
    nodes = node_tree.nodes
    nodes.clear()

    # Add Material Output node
    material_output = make_node(nodes, "ShaderNodeOutputMaterial", 0, 0)

    # Add an Emission Shader node
    emission = make_node(nodes, 'ShaderNodeEmission', -200, 0)

    # Add a math node for multiplication with light path
    math_lightpath = make_math_node(nodes, "MULTIPLY", -400, 0)
    light_path = make_node(nodes, "ShaderNodeLightPath", -600, 100)
    connect_nodes(node_tree, light_path, "Is Camera Ray", 0, math_lightpath)

    # Add a math node to control the intensity
    math_intensity = make_math_node(nodes, "MULTIPLY", -600, 0, default_2 = 15 * props.star_intensity)

    # Add a node group for random intensity
    group = bpy.data.node_groups.new("Random Intensity", "ShaderNodeTree")
    group_inputs = make_group_inputs(group, 0, 0, "Float", "Random")
    group_outputs = make_group_outputs(group, 1200, 0, "Float", "Intensity")
    # Add a math node to prepare random input
    math_inp_fact = make_math_node(group.nodes, "MULTIPLY", 200, 0, default_2 = 9100)
    # Add a math node to prepare input
    math_pre_div = make_math_node(group.nodes, "DIVIDE", 400, 0, default_2 = 3.56)
    # Add a math node to convert visual magnitude
    math_mag_log = make_math_node(group.nodes, "LOGARITHM", 600, 0, default_2 = math.e)
    # Add a math node to convert visual magnitude
    math_mag_div = make_math_node(group.nodes, "DIVIDE", 800, 0, default_2 = -1.21)
    # Add a math node to convert visual magnitude
    math_mag_power = make_math_node(group.nodes, "POWER", 1000, 0, default_1 = 2.512)
    # Connect nodes
    connect_nodes(group, group_inputs, "Random",
        0, math_inp_fact, 0,
        0, math_pre_div, 0,
        0, math_mag_log, 0,
        0, math_mag_div, 0,
        1, math_mag_power, 0,
        "Intensity", group_outputs)
    # Add group
    random_magnitude = make_group_node(nodes, group, -800, 0)

    # Make node group to split single random value into two
    group = bpy.data.node_groups.new("Random Splitter", "ShaderNodeTree")
    group_inputs = make_group_inputs(group, 0, 0, "Float", "Random")
    group_outputs = make_group_outputs(group, 600, 0, "Float", "Random 1", "Float", "Random 2")
    # Multiplication by large factor
    math_rsplit_mult = make_math_node(group.nodes, "MULTIPLY", 200, -100, default_2 = 1000)
    # Use only decimals
    math_rsplit_mod = make_math_node(group.nodes, "MODULO", 400, -100, default_2 = 1)
    # Connect nodes
    connect_nodes(group, group_inputs, "Random", "Random 1", group_outputs)
    connect_nodes(group, group_inputs, "Random",
        0, math_rsplit_mult, 0,
        0, math_rsplit_mod, 0,
        "Random 2", group_outputs)
    # Add group
    random_splitter = make_group_node(nodes, group, -1000, 0)

    # Add geometry input node
    geometry_input = make_node(nodes, "ShaderNodeObjectInfo", -1200, 0)

    # Connect main node chain
    connect_nodes(node_tree, geometry_input, "Random",
        "Random", random_splitter, "Random 1",
        "Random", random_magnitude, "Intensity",
        0, math_intensity, 0,
        1, math_lightpath, 0,
        "Strength", emission, "Emission",
        "Surface", material_output)
    hide_node_outputs(light_path)
    hide_node_outputs(geometry_input)

    # Make node group for star color
    group = bpy.data.node_groups.new("Random Star Color", "ShaderNodeTree")
    group_inputs = make_group_inputs(group, 0, 0, "Float", "Random")
    group_outputs = make_group_outputs(group, 800, 0, "Color", "Color")
    # Color temperature width
    math_kelvin_width = make_math_node(group.nodes, "MULTIPLY", 200, 0, default_2 = 17000)
    # Color temperature offset
    math_kelvin_offset = make_math_node(group.nodes, "ADD", 400, 0, default_2 = 3000)
    # Blackbody color
    blackbody = make_node(group.nodes, "ShaderNodeBlackbody", 600, 0)
    # Connect nodes
    connect_nodes(group, group_inputs, "Random",
        0, math_kelvin_width, 0,
        0, math_kelvin_offset, 0,
        "Temperature", blackbody, "Color",
        "Color", group_outputs)
    # Add group
    random_color = make_group_node(nodes, group, -600, -200)

    # Connect color chain
    connect_nodes(node_tree, random_splitter, "Random 2",
        "Random", random_color, "Color",
        "Color", emission)

    # Set material
    template_obj.active_material = bpy.data.materials["Star Shader"]

    ### Constraints and relationships ######################################################

    # Add location constraint
    # This keeps the stars fixed relatve to the camera
    stars_obj.constraints.clear()
    if props.camera_lock:
        constraint = stars_obj.constraints.new(type="COPY_LOCATION")
        constraint.target = obj_camera = camera

    # Add driver to object scale for the stars
    # This makes the stars be as far away while still visible
    fcurves = stars_obj.driver_add("scale")
    for fcurve in fcurves:
        # Add a variable for the camera focal length
        var = fcurve.driver.variables.new()
        var.name = "s"
        var.type = "SINGLE_PROP"
        target = var.targets[0]
        target.id_type = "CAMERA"
        target.id = camera.data.id_data
        target.data_path = "clip_end"

        # Set the driver expression
        fcurve.driver.expression = "0.9 * s"

    # Add driver to object scale for the template
    # This keeps the star size independent from focal length and render resolution
    fcurves = template_obj.driver_add("scale")
    for fcurve in fcurves:
        # Add a variable for the camera focal length
        var = fcurve.driver.variables.new()
        var.name = "f"
        var.type = "SINGLE_PROP"
        target = var.targets[0]
        target.id_type = "CAMERA"
        target.id = camera.data.id_data
        target.data_path = "lens"

        # Add a variable for the render width
        var = fcurve.driver.variables.new()
        var.name = "x"
        var.type = "SINGLE_PROP"
        target = var.targets[0]
        target.id_type = "SCENE"
        target.id = bpy.context.scene.id_data
        target.data_path = "render.resolution_x"

        # Add a variable for the render height
        var = fcurve.driver.variables.new()
        var.name = "y"
        var.type = "SINGLE_PROP"
        target = var.targets[0]
        target.id_type = "SCENE"
        target.id = bpy.context.scene.id_data
        target.data_path = "render.resolution_y"

        # Add a variable for the resolution percentage
        var = fcurve.driver.variables.new()
        var.name = "p"
        var.type = "SINGLE_PROP"
        target = var.targets[0]
        target.id_type = "SCENE"
        target.id = bpy.context.scene.id_data
        target.data_path = "render.resolution_percentage"

        # Set the driver expression
        fcurve.driver.expression = "50 / f * 2202.907 / max(x, y) / p * 100"

    # Set object relationship
    template_obj.parent = stars_obj
    stars_obj.instance_type = "VERTS"
    stars_obj.use_instance_vertices_rotation = True
    #stars_obj.show_instancer_for_viewport = False
    stars_obj.show_instancer_for_render = False

    # Hide the template
    template_obj.hide_viewport = True
    #template_obj.hide_render = True
    # Add the object

    # Clear the world background
    if props.clear_world_bg:
        # Turn nodes off
        bpy.context.world.use_nodes = False
        # Set color to pure black
        bpy.context.world.color = (0.0, 0.0, 0.0)

    return True

if __name__ == "__main__":
    generate_starscape()
