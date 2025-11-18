#pragma once

#include <cctype>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <map>
#include <stdexcept>
#include <string>
#include <variant>
#include <vector>
#include <istream>
#include <sstream>
#include <type_traits>

namespace nlohmann {

class json {
public:
    using object_t = std::map<std::string, json>;
    using array_t = std::vector<json>;
    using string_t = std::string;
    using boolean_t = bool;
    using number_t = double;

    json() : data_(nullptr) {}
    json(std::nullptr_t) : data_(nullptr) {}
    json(boolean_t b) : data_(b) {}
    json(int v) : data_(static_cast<number_t>(v)) {}
    json(int64_t v) : data_(static_cast<number_t>(v)) {}
    json(double v) : data_(v) {}
    json(const char* s) : data_(string_t(s)) {}
    json(const string_t& s) : data_(s) {}
    json(array_t arr) : data_(std::move(arr)) {}
    json(object_t obj) : data_(std::move(obj)) {}
    json(std::initializer_list<std::pair<const std::string, json>> init) : data_(object_t{}) {
        auto& obj = std::get<object_t>(data_);
        for (const auto& p : init) {
            obj.emplace(p.first, p.second);
        }
    }

    static json parse(const std::string& text) {
        struct Parser {
            const std::string& s;
            size_t pos{0};

            void skip_ws() {
                while (pos < s.size() && std::isspace(static_cast<unsigned char>(s[pos]))) ++pos;
            }

            char peek() {
                if (pos >= s.size()) throw std::runtime_error("Unexpected end of input");
                return s[pos];
            }

            bool consume(char c) {
                if (peek() == c) { ++pos; return true; }
                return false;
            }

            json parse_value() {
                skip_ws();
                char c = peek();
                if (c == '{') return parse_object();
                if (c == '[') return parse_array();
                if (c == '"') return parse_string();
                if (c == 't' || c == 'f' || c == 'n') return parse_literal();
                return parse_number();
            }

            json parse_object() {
                consume('{');
                object_t obj;
                skip_ws();
                if (consume('}')) return obj;
                while (true) {
                    skip_ws();
                    auto key = parse_string().get<string_t>();
                    skip_ws();
                    if (!consume(':')) throw std::runtime_error("Expected ':' in object");
                    obj[key] = parse_value();
                    skip_ws();
                    if (consume('}')) break;
                    if (!consume(',')) throw std::runtime_error("Expected ',' in object");
                }
                return obj;
            }

            json parse_array() {
                consume('[');
                array_t arr;
                skip_ws();
                if (consume(']')) return arr;
                while (true) {
                    arr.push_back(parse_value());
                    skip_ws();
                    if (consume(']')) break;
                    if (!consume(',')) throw std::runtime_error("Expected ',' in array");
                }
                return arr;
            }

            json parse_string() {
                if (!consume('"')) throw std::runtime_error("Expected '\"' to start string");
                std::string out;
                while (pos < s.size()) {
                    char c = s[pos++];
                    if (c == '"') break;
                    if (c == '\\') {
                        if (pos >= s.size()) throw std::runtime_error("Bad escape");
                        char esc = s[pos++];
                        switch (esc) {
                            case '"': out.push_back('"'); break;
                            case '\\': out.push_back('\\'); break;
                            case '/': out.push_back('/'); break;
                            case 'b': out.push_back('\b'); break;
                            case 'f': out.push_back('\f'); break;
                            case 'n': out.push_back('\n'); break;
                            case 'r': out.push_back('\r'); break;
                            case 't': out.push_back('\t'); break;
                            default: throw std::runtime_error("Unsupported escape");
                        }
                    } else {
                        out.push_back(c);
                    }
                }
                return out;
            }

            json parse_literal() {
                if (s.compare(pos, 4, "true") == 0) { pos += 4; return json(true); }
                if (s.compare(pos, 5, "false") == 0) { pos += 5; return json(false); }
                if (s.compare(pos, 4, "null") == 0) { pos += 4; return json(nullptr); }
                throw std::runtime_error("Invalid literal");
            }

            json parse_number() {
                size_t start = pos;
                if (s[pos] == '-') ++pos;
                while (pos < s.size() && std::isdigit(static_cast<unsigned char>(s[pos]))) ++pos;
                if (pos < s.size() && s[pos] == '.') {
                    ++pos;
                    while (pos < s.size() && std::isdigit(static_cast<unsigned char>(s[pos]))) ++pos;
                }
                double value = std::stod(s.substr(start, pos - start));
                return json(value);
            }
        } parser{text};

        parser.skip_ws();
        json result = parser.parse_value();
        parser.skip_ws();
        return result;
    }

    bool is_object() const { return std::holds_alternative<object_t>(data_); }
    bool is_array() const { return std::holds_alternative<array_t>(data_); }
    bool is_string() const { return std::holds_alternative<string_t>(data_); }

    size_t size() const {
        if (is_array()) return std::get<array_t>(data_).size();
        if (is_object()) return std::get<object_t>(data_).size();
        return 0;
    }

    bool contains(const std::string& key) const {
        if (!is_object()) return false;
        const auto& obj = std::get<object_t>(data_);
        return obj.find(key) != obj.end();
    }

    json& operator[](const std::string& key) {
        if (!is_object()) data_ = object_t{};
        return std::get<object_t>(data_)[key];
    }

    const json& at(const std::string& key) const {
        return std::get<object_t>(data_).at(key);
    }

    const json& operator[](const std::string& key) const {
        return at(key);
    }

    json& operator[](size_t idx) {
        if (!is_array()) throw std::runtime_error("not an array");
        auto& arr = std::get<array_t>(data_);
        if (idx >= arr.size()) throw std::out_of_range("index");
        return arr[idx];
    }

    const json& operator[](size_t idx) const {
        return const_cast<json&>(*this)[idx];
    }

    array_t::const_iterator begin() const {
        if (!is_array()) throw std::runtime_error("not an array");
        return std::get<array_t>(data_).begin();
    }

    array_t::const_iterator end() const {
        if (!is_array()) throw std::runtime_error("not an array");
        return std::get<array_t>(data_).end();
    }

    template <typename T>
    T get() const {
        if constexpr (std::is_same_v<T, string_t>) {
            if (!is_string()) throw std::runtime_error("not a string");
            return std::get<string_t>(data_);
        } else if constexpr (std::is_same_v<T, bool>) {
            if (!std::holds_alternative<boolean_t>(data_)) throw std::runtime_error("not a bool");
            return std::get<boolean_t>(data_);
        } else if constexpr (std::is_integral_v<T>) {
            if (std::holds_alternative<number_t>(data_)) return static_cast<T>(std::get<number_t>(data_));
            throw std::runtime_error("not a number");
        } else if constexpr (std::is_floating_point_v<T>) {
            if (std::holds_alternative<number_t>(data_)) return static_cast<T>(std::get<number_t>(data_));
            throw std::runtime_error("not a number");
        } else {
            static_assert(sizeof(T) == 0, "Unsupported get type");
        }
    }

    template <typename T>
    T value(const std::string& key, T default_value) const {
        if (!contains(key)) return default_value;
        return at(key).get<T>();
    }

    std::string value(const std::string& key, const char* default_value) const {
        if (!contains(key)) return std::string(default_value);
        return at(key).get<string_t>();
    }

    std::string dump(int indent = -1) const {
        (void)indent;
        std::ostringstream oss;
        if (is_object()) {
            oss << '{';
            bool first = true;
            for (const auto& [k, v] : std::get<object_t>(data_)) {
                if (!first) oss << ',';
                first = false;
                oss << '"' << k << '"' << ':' << v.dump();
            }
            oss << '}';
        } else if (is_array()) {
            oss << '[';
            const auto& arr = std::get<array_t>(data_);
            for (size_t i = 0; i < arr.size(); ++i) {
                if (i > 0) oss << ',';
                oss << arr[i].dump();
            }
            oss << ']';
        } else if (std::holds_alternative<string_t>(data_)) {
            oss << '"' << std::get<string_t>(data_) << '"';
        } else if (std::holds_alternative<number_t>(data_)) {
            oss << std::get<number_t>(data_);
        } else if (std::holds_alternative<boolean_t>(data_)) {
            oss << (std::get<boolean_t>(data_) ? "true" : "false");
        } else {
            oss << "null";
        }
        return oss.str();
    }

    friend std::istream& operator>>(std::istream& is, json& j) {
        std::ostringstream oss;
        oss << is.rdbuf();
        j = json::parse(oss.str());
        return is;
    }

private:
    std::variant<std::nullptr_t, boolean_t, number_t, string_t, array_t, object_t> data_;
};

} // namespace nlohmann

