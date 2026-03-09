#include <cstddef>

template <typename T>
struct MyListNode {
  T value;
  MyListNode* next;
};

template <typename T>
struct MyList {
  MyListNode<T>* head;
  std::size_t size;
};

template <typename T>
struct MyTreeNode {
  T value;
  MyTreeNode* left;
  MyTreeNode* right;
};

template <typename T>
struct MyBinaryTree {
  MyTreeNode<T>* root;
  std::size_t size;
};

template <typename T>
struct MyGraphNode {
  T value;
  MyGraphNode<T>* neighbors[2];
};

template <typename T>
struct MyGraph {
  MyGraphNode<T>* nodes[3];
  std::size_t num_nodes;
  std::size_t num_edges;
};

[[gnu::noinline]] void break_here() {}

int main() {
  auto* list_node3 = new MyListNode<int>{30, nullptr};
  auto* list_node2 = new MyListNode<int>{20, list_node3};
  auto* list_node1 = new MyListNode<int>{10, list_node2};
  MyList<int> my_list{list_node1, 3};

  auto* tree_node1 = new MyTreeNode<int>{1, nullptr, nullptr};
  auto* tree_node3 = new MyTreeNode<int>{3, nullptr, nullptr};
  auto* tree_root = new MyTreeNode<int>{2, tree_node1, tree_node3};
  MyBinaryTree<int> my_tree{tree_root, 3};

  auto* graph_node3 = new MyGraphNode<int>{30, {nullptr, nullptr}};
  auto* graph_node2 = new MyGraphNode<int>{20, {graph_node3, nullptr}};
  auto* graph_node1 = new MyGraphNode<int>{10, {graph_node2, graph_node3}};
  MyGraph<int> my_graph{{graph_node1, graph_node2, graph_node3}, 3, 3};

  break_here();

  volatile auto keep_alive =
      my_list.size + my_tree.size + my_graph.num_nodes + my_graph.num_edges;
  return static_cast<int>(keep_alive);
}
