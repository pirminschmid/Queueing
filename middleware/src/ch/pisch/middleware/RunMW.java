package ch.pisch.middleware;

import ch.pisch.middleware.mw.MyMiddleware;

import java.util.*;

public class RunMW {

	public static class Parameters {
		public String myIp = null;
		public int myPort = 0;
		public List<String> mcAddresses = null;
		public int numThreadsPTP = -1;
		public boolean readSharded = false;
	}

	public static void main(String[] args) {
		Parameters p = parseArguments(args);
		MyMiddleware m = new MyMiddleware(p.myIp, p.myPort, p.mcAddresses, p.numThreadsPTP, p.readSharded);
		m.run();
	}

	private static Parameters parseArguments(String[] args) {
		Parameters p = new Parameters();
		Map<String, List<String>> params = new HashMap<>();

		List<String> options = null;
		for (String a : args) {
			if (a.startsWith("-")) {
				if (a.length() < 2) {
					printError("Error at argument " + a);
				}

				options = new ArrayList<>();
				params.put(a.substring(1), options);
			} else if (options != null) {
				options.add(a);
			} else {
				printError("Illegal parameter usage");
			}
		}

		if (params.size() == 0) {
			printError(null);
		}

		if (params.get("l") != null) {
			p.myIp = params.get("l").get(0);
		} else {
			printError("Middleware IP address missing, e.g. -l 127.0.0.1.");
		}

		if (params.get("p") != null) {
			p.myPort = Integer.parseInt(params.get("p").get(0));
		} else {
			printError("Middleware port number missing, e.g. -p 11211.");
		}

		if (params.get("m") != null) {
			p.mcAddresses = params.get("m");
		} else {
			printError(" At least one memcached backend server IP address and port is required, e.g. -m 123.11.11.10:11211");
		}

		if (params.get("t") != null) {
			p.numThreadsPTP = Integer.parseInt(params.get("t").get(0));
		} else {
			printError("Number of worker threads, e.g. -t 8");
		}

		if (params.get("s") != null) {
			p.readSharded = Boolean.parseBoolean(params.get("s").get(0));
		} else {
			printError("Sharded reads?, either -s true / -s false");
		}

		return p;
	}

	private static void printError(String errorMessage) {
		System.err.println();
		System.err.println(
				"Usage: -l <IP address> -p <Port> -t <NumberOfThreads> -s <readSharded: true/false> -m <memcachedIP1:Port1> <memcachedIP2:Port2> ...");
		if (errorMessage != null) {
			System.err.println();
			System.err.println("Error message: " + errorMessage);
		}
		System.exit(1);
	}
}
