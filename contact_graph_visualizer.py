# CGR
from sys import maxsize
from os import access, R_OK, path, makedirs
from py_cgr_lib import Contact, Route

# Plotting graphs
import matplotlib.pyplot as plt
import networkx as nx

import json
import argparse

def dijkstra(root_contact, destination, contact_plan):
    # modified from https://bitbucket.org/juanfraire/pycgr/src/master/
    src_id = (str(int(root_contact.id))) if isinstance(root_contact.id, float) else root_contact.id
    print("Looking for routes from %s to %s" % (src_id, destination))
    def get_route(start_contact, end_contact):
        hops = []
        contact = end_contact
        while contact != start_contact:
            hops.insert(0, contact)
            contact = contact.predecessor
        route = Route(hops[0])
        for hop in hops[1:]:
            route.append(hop)
        return route

    for contact in contact_plan:
        contact.clear_dijkstra_working_area()

    contact_plan_hash = {}
    for contact in contact_plan:
        if contact.frm not in contact_plan_hash:
            contact_plan_hash[contact.frm] = []
        if contact.to not in contact_plan_hash:
            contact_plan_hash[contact.to] = []
        contact_plan_hash[contact.frm].append(contact)

    current = root_contact
    if root_contact.to not in root_contact.visited_nodes:
        root_contact.visited_nodes.append(root_contact.to)

    debug = False

    all_routes = []
    route = None
    best_final_contact = None
    earliest_fin_arr_t = maxsize
    while True:
        if debug:
            print("\t\t\tCurrent contact: ", current)
        # Calculate cost of all proximate contacts
        for contact in contact_plan_hash[current.to]:
            if debug:
                print("\t\t\t\tExplore contact: ", contact, " - ", end='')
            if contact in current.suppressed_next_hop:
                if debug:
                    print("\t\t\t\tignore (suppressed_next_hop - Yens')")
                continue
            if contact.suppressed:
                if debug:
                    print("\t\t\t\tignore (suppressed)")
                continue
            if contact.visited:
                if debug:
                    print("\t\t\t\tignore (contact visited)")
                continue
            if contact.to in current.visited_nodes:
                if debug:
                    print("\t\t\t\tignore (node visited)")
                continue
            if contact.end <= current.arrival_time:  # <= important!
                if debug:
                    print("\t\t\t\tignore (contact ends before arrival_time)", contact.end, current.arrival_time)
                continue
            if max(contact.mav) <= 0:
                if debug:
                    print("\t\t\t\tignore (no residual volume)")
                continue
            if current.frm == contact.to and current.to == contact.frm:
                if debug:
                    print("\t\t\t\tignore (return to previous node)")
                continue
            if debug:
                print("\t\t\t\tcontact not ignored - ", end='')

            # Calculate arrival time (cost)
            if contact.start < current.arrival_time:
                arrvl_time = current.arrival_time + contact.owlt
                if debug:
                    print("arrival_time: ", arrvl_time, " - ", end='')
            else:
                arrvl_time = contact.start + contact.owlt
                if debug:
                    print("arrival_time: ", arrvl_time, " - ", end='')

            # Update cost if better or equal
            if arrvl_time <= contact.arrival_time:
                if debug:
                    print("updated from: ", contact.arrival_time, " - ", end='')
                contact.arrival_time = arrvl_time
                contact.predecessor = current
                contact.visited_nodes = current.visited_nodes[:]
                contact.visited_nodes.append(contact.to)
                if debug:
                    print("visited nodes: ", contact.visited_nodes, " - ", end='')

                # Mark if destination reached
                
                if contact.to == destination:
                    all_routes.append(get_route(root_contact, contact))
                if contact.to == destination and contact.arrival_time < earliest_fin_arr_t:
                    if debug:
                        print("marked as final! - ", end='')
                    earliest_fin_arr_t = contact.arrival_time
                    best_final_contact = contact
            else:
                if debug:
                    print("not updated (previous: ", contact.arrival_time, ") - ", end='')

            if debug:
                print("done")

        if debug:
            print("\t\t\tSet current visited true for ", current)
        current.visited = True

        # Determine best next contact among all in contactPlan
        earliest_arr_t = maxsize
        next_contact = 0

        for contact in contact_plan:

            # Ignore suppressed, visited
            if contact.suppressed or contact.visited:
                if debug:
                    print("\t\t\t\t Ignoring bc suppressed or visited ", contact)
                continue

            # If we know there is another better contact, continue
            if contact.arrival_time > earliest_fin_arr_t:
                if debug:
                    print("\t\t\t\t Ignoring bc arrival time not good enough %s (%d > %d)" % (contact, contact.arrival_time, earliest_fin_arr_t))
                continue

            if contact.arrival_time < earliest_arr_t:
                earliest_arr_t = contact.arrival_time
                next_contact = contact
                if debug:
                    print("   Next contact set to: ", next_contact)

        if next_contact == 0:
            if debug:
                print("   No next contact found")
            break
        current = next_contact

    # Done contact graph exploration, check and store new route
    if best_final_contact is not None:
        hops = []
        contact = best_final_contact
        while contact != root_contact:
            hops.insert(0, contact)
            contact = contact.predecessor

        # print("route:", hops)
        route = Route(hops[0])
        for hop in hops[1:]:
            route.append(hop)
    
    if route is None:
        src_id = (str(int(root_contact.id))) if isinstance(root_contact.id, float) else root_contact.id
        print("Could not find any routes from %s to %s" % (src_id, destination))
        return None
    else:
        return all_routes

def load_contactplan(filename):
    with open(filename, "r") as read_file:
        data = json.load(read_file)
        contacts = data["contacts"]
        contact_plan = []
        for contact in contacts:
            contact_plan.append(
                Contact(
                    start=contact["startTime"],
                    end=contact["endTime"],
                    frm=contact["source"],
                    to=contact["dest"],
                    rate=contact["rate"],
                    owlt=contact["owlt"],
                    id=contact["contact"]))
        return contact_plan

def get_all_node_ids(contact_plan):
    all_node_ids = set()
    for c in contact_plan:
        all_node_ids.add(c.frm)
        all_node_ids.add(c.to)
    return list(all_node_ids)

def draw_graph(layers, edges, best_edges, labels):
    G = nx.DiGraph()
    for (i, layer) in enumerate(layers):
        G.add_nodes_from(layer, layer=i)
    G.add_edges_from(edges, weight=1)
    G.add_edges_from(best_edges, weight=55)

    pos = nx.multipartite_layout(G, subset_key="layer")
    elarge = [(u, v) for (u, v, d) in G.edges(data=True) if d["weight"] > 50]
    esmall = [(u, v) for (u, v, d) in G.edges(data=True) if d["weight"] <= 50]
    nx.draw_networkx_edges(G, pos, edgelist=esmall, alpha = 0.5, width = 5, edge_color="red")
    nx.draw_networkx_edges(G, pos, edgelist=elarge, alpha = 0.5, width = 5, edge_color="green")
    nx.draw(G, pos, node_size=1, with_labels=True, labels=labels, font_size=12)

def draw_all_routes(src_node, dst_node, all_routes):
    max_layers = 0
    fastest_bdt = 0
    for r in all_routes:
        max_layers = max(len(r.get_hops()), max_layers)
        fastest_bdt = max(r.best_delivery_time, fastest_bdt)
    layers = [[] for i in range(max_layers)]
    edges = []
    best_edges = []
    labeldict = {}
    root_contact_id = -1
    terminal_contact_id = -2
    layers.insert(0, [root_contact_id])
    layers.append([terminal_contact_id])
    labeldict[root_contact_id] = str(src_node) + "->" + str(src_node)
    labeldict[terminal_contact_id] = str(dst_node) + "->" + str(dst_node)
    for r in all_routes:
        edg = best_edges if (r.best_delivery_time == fastest_bdt) else edges
        hops = r.get_hops()
        for layer_index, h in enumerate(r.get_hops()):
            labeldict[h.id] = str(h.id) + "\n[" + str(h.frm) + "→" + str(h.to) + "]"
            layers[layer_index + 1].append(h.id)
            if layer_index == 0:
                edg.append((root_contact_id, h.id))
            if layer_index == (len(hops) - 1):
                edg.append((h.id, terminal_contact_id))
            if layer_index > 0:
                edg.append((hops[layer_index - 1].id, h.id))
    draw_graph(layers, edges, best_edges, labeldict)

def from_src_to_dst(output_dir, contact_plan_filename, src_id, dst_id, contact_plan):
    print("Finding all routes from %s to %s..." % (src_id, dst_id))
    root_contact = Contact(frm=src_id, to=src_id, start=0, end=maxsize, rate=100, id=src_id, confidence=1.0, owlt=0)
    root_contact.arrival_time = 0
    all_routes = dijkstra(root_contact, dst_id, contact_plan)
    plt.figure(figsize=(16, 8))
    draw_all_routes(src_id, dst_id, all_routes)
    plt.suptitle("%s\nroutes from %s to %s" % (contact_plan_filename, src_id, dst_id), fontsize="xx-large", fontweight="bold")
    plt.savefig(output_dir + "%s-routes-from-%s-to-%s.png" % (contact_plan_filename, src_id, dst_id))

def from_src_to_all(output_dir, contact_plan_filename, src_id, contact_plan):
    print("Finding all routes from %s to all..." % (src_id))
    all_node_ids = get_all_node_ids(contact_plan)
    all_pairs_with_src = [(src_id, nid) for nid in all_node_ids if nid != src_id]
    data = []
    print(all_pairs_with_src)
    for i, pair in enumerate(all_pairs_with_src):
        src, dst = pair
        root_contact = Contact(frm=src, to=src, start=0, end=maxsize, rate=100, id=src, confidence=1.0, owlt=0)
        root_contact.arrival_time = 0
        all_routes = dijkstra(root_contact, dst, contact_plan)
        if all_routes is not None:
            data.append((src, dst, all_routes))

    if len(data) == 0:
        print("No routes could be found starting from %s" % src_id)
        return
    num_rows = (len(data) // 2) if len(data) % 2 == 0 else (len(data) // 2) + 1
    num_cols = 2
    fig, axs = plt.subplots(num_rows, num_cols, figsize=(num_cols * 10, num_cols * 8))
    for i, route_result in enumerate(data):
        src, dst, all_routes = route_result
        plt.subplot(num_rows, num_cols, i + 1)
        draw_all_routes(src, dst, all_routes)
    fig.suptitle("%s\nroutes from %s to all" % (contact_plan_filename, src_id), fontsize="xx-large", fontweight="bold")
    plt.savefig(output_dir + "%s-routes-from-%s-to-all.png" % (contact_plan_filename, src_id))

def from_all_to_dst(output_dir, contact_plan_filename, dst_id, contact_plan):
    print("Finding all routes from all to %s..." % (dst_id))
    all_node_ids = get_all_node_ids(contact_plan)
    all_pairs_with_dst = [(nid, dst_id) for nid in all_node_ids if nid != dst_id]
    data = []
    print(all_pairs_with_dst)
    for i, pair in enumerate(all_pairs_with_dst):
        src, dst = pair
        root_contact = Contact(frm=src, to=src, start=0, end=maxsize, rate=100, id=src, confidence=1.0, owlt=0)
        root_contact.arrival_time = 0
        all_routes = dijkstra(root_contact, dst, contact_plan)
        if all_routes is not None:
            data.append((src, dst, all_routes))

    if len(data) == 0:
        print("No routes could be found towards %s" % dst_id)
        return
    num_rows = (len(data) // 2) if len(data) % 2 == 0 else (len(data) // 2) + 1
    num_cols = 2
    fig, axs = plt.subplots(num_rows, num_cols, figsize=(num_cols * 10, num_cols * 8))
    for i, route_result in enumerate(data):
        src, dst, all_routes = route_result
        plt.subplot(num_rows, num_cols, i + 1)
        draw_all_routes(src, dst, all_routes)
    fig.suptitle("%s\nroutes from all to %s" % (contact_plan_filename, dst_id), fontsize="xx-large", fontweight="bold")
    plt.savefig(output_dir + "%s-routes-from-all-to-%s.png" % (contact_plan_filename, dst_id))

def from_all_to_all(output_dir, contact_plan_filename, contact_plan):
    print("Finding all routes from all to all...")
    all_node_ids = get_all_node_ids(contact_plan)
    print(all_node_ids)
    for nid in all_node_ids:
        from_src_to_all(output_dir, contact_plan_filename, nid, contact_plan)
        from_all_to_dst(output_dir, contact_plan_filename, nid, contact_plan)

def main():
    argParser = argparse.ArgumentParser()
    argParser.add_argument("file", help="File path of the contact plan")
    argParser.add_argument("--src", help="ID of the source node")
    argParser.add_argument("--dst", help="ID of the destination node")
    argParser.add_argument("--dir", help="Output directory to store plots in", default="./out/")
    args = argParser.parse_args()
    if not access(args.file, R_OK):
        print("Couldn't open file: %s" % args.file)
        quit()
    out_dir = path.join(args.dir, "") # to make sure path ends with /
    if not path.exists(out_dir):
        makedirs(out_dir)
    contact_plan = load_contactplan(args.file)
    contact_plan_filename = path.splitext(path.split(args.file)[1])[0]

    if args.src is not None:
        src_node = int(args.src) if (str.isdigit(args.src)) else args.src
        if args.dst is not None:
            dst_node = int(args.dst) if (str.isdigit(args.dst)) else args.dst
            from_src_to_dst(out_dir, contact_plan_filename, src_node, dst_node, contact_plan)
        else:
            from_src_to_all(out_dir, contact_plan_filename, src_node, contact_plan)
    elif args.dst is not None:
        dst_node = int(args.dst) if (str.isdigit(args.dst)) else args.dst
        from_all_to_dst(out_dir, contact_plan_filename, dst_node, contact_plan)
    else:
        from_all_to_all(out_dir, contact_plan_filename, contact_plan)
    
if __name__ == "__main__":
    main()