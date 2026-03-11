#include <cstddef>
#include <memory>
#include <optional>
#include <string>
#include <utility>

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
struct MyLinkedListNode {
  T value;
  std::unique_ptr<MyLinkedListNode<T>> next;
};

template <typename T>
struct MyLinkedList {
  std::unique_ptr<MyLinkedListNode<T>> head;
  std::size_t size;
};

template <typename T>
struct SmartTreeNode {
  T value;
  std::unique_ptr<SmartTreeNode<T>> left;
  std::unique_ptr<SmartTreeNode<T>> right;
};

template <typename T>
struct MyTree {
  std::unique_ptr<SmartTreeNode<T>> root;
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

  auto* string_node3 =
      new MyListNode<std::string>{std::string("gamma"), nullptr};
  auto* string_node2 =
      new MyListNode<std::string>{std::string("beta"), string_node3};
  auto* string_node1 =
      new MyListNode<std::string>{std::string("alpha"), string_node2};
  MyList<std::string> my_string_list{string_node1, 3};

  auto* optional_node3 =
      new MyListNode<std::optional<int>>{std::optional<int>{30}, nullptr};
  auto* optional_node2 =
      new MyListNode<std::optional<int>>{std::nullopt, optional_node3};
  auto* optional_node1 =
      new MyListNode<std::optional<int>>{std::optional<int>{10}, optional_node2};
  MyList<std::optional<int>> my_optional_list{optional_node1, 3};

  auto smart_list_node3 = std::make_unique<MyLinkedListNode<int>>(
      MyLinkedListNode<int>{30, nullptr});
  auto smart_list_node2 = std::make_unique<MyLinkedListNode<int>>(
      MyLinkedListNode<int>{20, std::move(smart_list_node3)});
  MyLinkedList<int> my_smart_list{
      std::make_unique<MyLinkedListNode<int>>(
          MyLinkedListNode<int>{10, std::move(smart_list_node2)}),
      3};

  auto* tree_node1 = new MyTreeNode<int>{1, nullptr, nullptr};
  auto* tree_node3 = new MyTreeNode<int>{3, nullptr, nullptr};
  auto* tree_root  = new MyTreeNode<int>{2, tree_node1, tree_node3};
  MyBinaryTree<int> my_tree{tree_root, 3};

  auto* pair_tree_node1 =
      new MyTreeNode<std::pair<int, int>>{{1, 10}, nullptr, nullptr};
  auto* pair_tree_node3 =
      new MyTreeNode<std::pair<int, int>>{{3, 30}, nullptr, nullptr};
  auto* pair_tree_root =
      new MyTreeNode<std::pair<int, int>>{{2, 20}, pair_tree_node1, pair_tree_node3};
  MyBinaryTree<std::pair<int, int>> my_pair_tree{pair_tree_root, 3};

  auto smart_tree_root = std::make_unique<SmartTreeNode<int>>(SmartTreeNode<int>{
      2,
      std::make_unique<SmartTreeNode<int>>(SmartTreeNode<int>{1, nullptr, nullptr}),
      std::make_unique<SmartTreeNode<int>>(SmartTreeNode<int>{3, nullptr, nullptr}),
  });
  MyTree<int> my_smart_tree{std::move(smart_tree_root), 3};

  auto* graph_node3 = new MyGraphNode<int>{30, {nullptr, nullptr}};
  auto* graph_node2 = new MyGraphNode<int>{20, {graph_node3, nullptr}};
  auto* graph_node1 = new MyGraphNode<int>{10, {graph_node2, graph_node3}};
  MyGraph<int> my_graph{{graph_node1, graph_node2, graph_node3}, 3, 3};

  break_here();

  volatile auto keep_alive =
      my_list.size + my_string_list.size + my_optional_list.size +
      my_smart_list.size + my_tree.size + my_pair_tree.size +
      my_smart_tree.size + my_graph.num_nodes + my_graph.num_edges;
  return static_cast<int>(keep_alive);
}
