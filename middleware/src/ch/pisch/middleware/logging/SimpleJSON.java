package ch.pisch.middleware.logging;

import java.util.Collection;
import java.util.HashMap;
import java.util.Map;

/**
 * Simple helper class to write JSON files.
 * Features:
 * - nested JSON objects
 * - collections (treated as arrays)
 * - numbers: int, long, float, double
 * - boolean
 * - objects with toString() returning the proper format
 *
 * version 2018-11-22, Pirmin Schmid
 */

public class SimpleJSON {
    private static final String TAG = "SimpleJSON";
    private static final String kSpaces_20 = "                    ";
    private static final String kSpaces = kSpaces_20 + kSpaces_20 + kSpaces_20 + kSpaces_20;
    private static final int kMaxNested = 40;
    private static final int kIndent = 2;
    private static final String kFloatFormat = "%.1f";
    private final HashMap<String, Object> map = new HashMap<>();

    public SimpleJSON() {}

    public void put(String key, Object value) {
        map.put(key, value);
    }

    public Object get(String key) {
        return map.get(key);
    }

    public boolean containsKey(String key) {
        return map.containsKey(key);
    }

    private String handleObject(Object o, int nested) {
        if (o instanceof  SimpleJSON) {
            SimpleJSON j = (SimpleJSON) o;
            return j.toJSON(nested);
        }
        if (o instanceof Integer || o instanceof Long || o instanceof Boolean) {
            return o.toString();
        }

        if (o instanceof Float) {
            return String.format(kFloatFormat, (Float)o);
        }

        if (o instanceof Double) {
            return String.format(kFloatFormat, (Double)o);
        }

        if (o instanceof Collection<?>) {
            Collection<?> c = (Collection<?>)o;
            int n = c.size();
            StringBuilder sb = new StringBuilder();
            sb.append("[\n");
            int i = 0;
            for (Object obj : c) {
                i++;
                int array_nested = nested + 1;
                sb.append(kSpaces, 0, array_nested * kIndent)
                        .append(handleObject(obj, array_nested));
                if (i < n) {
                    sb.append(",");
                }
                sb.append("\n");
            }
            sb.append(kSpaces, 0, nested * kIndent).append("]");
            return sb.toString();
        }

        return "\"" + o.toString() + "\"";
    }

    public String toJSON(int nested) {
        if (nested < 0) {
            nested = 0;
        }
        if (nested > kMaxNested) {
            nested = kMaxNested;
        }

        StringBuilder sb = new StringBuilder();
        sb.append("{\n"); // no indent needed here
        nested++;

        int n = map.size();
        int i = 0;
        for (Map.Entry<String, Object> entry : map.entrySet()) {
            i++;
            sb.append(kSpaces, 0, nested * kIndent)
                    .append("\"")
                    .append(entry.getKey())
                    .append("\": ")
                    .append(handleObject(entry.getValue(), nested));
            if (i < n) {
                sb.append(",");
            }
            sb.append("\n");
        }

        nested--;
        sb.append(kSpaces, 0, nested * kIndent).append("}");
        if (nested == 0) {
            sb.append("\n");
        }
        return sb.toString();
    }

    @Override
    public String toString() {
        return toJSON(0);
    }
}
