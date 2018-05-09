
# coding: utf-8

# In[11]:


import pandas as pd
import numpy as np
import collections
import dpkt


# In[12]:


from protocolnumber2name import *
from portnumber2name import *
from tcpflagletters2names import *
from pcap2dataframe import *
from pcapng2dataframe import *
# from functions.sflow2dataframe import *
# from functions.nfdump2dataframe import *


# In[13]:


def analyse_df_pcap(df, debug=False, ttl_variation_threshold = 4):
    """
    Analysis only top traffic stream

    :param dataframe (df) containing the pcap/pcapng file converted:
    :return (1) print the summary of attack vectors and :
    """

    attack_case = "-1"
    reflection_label=""
    spoofed_label=""
    fragment_label=""

    allpatterns = {
        "dst_ip" : "",
        "patterns": []
    }    
    
    if debug: print "Total number packets: "+ str(len(df))
    if debug: print "\n###################################\nIDENTIFYING MAIN CHARACTERISTICS:\n###################################"
    
    top_dst_ip = df['dst_ip'].value_counts().index[0]
    
    if debug: print "Target (destination) IP: " + top_dst_ip
    allpatterns["dst_ip"] = top_dst_ip
    
    df_filtered = df[(df['dst_ip'] == top_dst_ip) ]
    
    total_packets_to_target = len(df_filtered)
    if debug: print "Number of packets: "+str(total_packets_to_target)    
    
    while (len(df_filtered)>0):
        if debug: print "\n###################################################################################################################"
        
        result = {}
        top_ip_proto = df[df['dst_ip'] == top_dst_ip]['ip_proto'].value_counts().index[0]
        result['ip_protocol']=top_ip_proto
        
        if debug: print "IP protocol used in packets going to target IP: "+str(top_ip_proto)
        
        df_filtered = df_filtered[df_filtered['ip_proto'] == top_ip_proto]

        # Performing a first filter based on the top_dst_ip (target IP), the source IPs can NOT be from the \16 of the
        # target IP, and the top IP protocol that targeted the top_dst_ip

        # Calculating the number of packets after the first filter 
        total_packets_filtered = len(df_filtered)
        if debug: print "Number of packets: "+str(total_packets_filtered)
        result["total_nr_packets"] = total_packets_filtered
    
        # For attacks in the IP protocol level
        attack_label = protocolnumber2name(top_ip_proto) + "-based attack"
        result["transport_protocol"] = protocolnumber2name(top_ip_proto)

        # For attacks based on TCP or UDP, which have source and destination ports
        if ((top_ip_proto == 6) or (top_ip_proto == 17)):

            if debug: print "\n#############################\nPORT FREQUENCY OF REMAINING PACKETS\n##############################"
                
            # Calculating the distribution of source ports based on the first filter
            percent_src_ports = df_filtered['src_port'].value_counts().divide(float(total_packets_filtered) / 100)

            if debug: print "SOURCE ports frequency" 
            if debug: print percent_src_ports.head() 

            # Calculating the distribution of destination ports after the first filter
            percent_dst_ports = df_filtered['dst_port'].value_counts().divide(float(total_packets_filtered) / 100)

            if debug: print "\nDESTINATION ports frequency" 
            if debug: print percent_dst_ports.head()

            ## WARNING packets are filtered here again
            # Using the top 1 (source or destination) port to analyse a pattern of packets
            if (len(percent_src_ports) > 0) and (len(percent_dst_ports) > 0):
                if percent_src_ports.values[0] > percent_dst_ports.values[0]:
                    if debug: print "\nUsing top source port: ", percent_src_ports.keys()[0] 
                    df_pattern = df_filtered[df_filtered['src_port'] == percent_src_ports.keys()[0]]
                    result["selected_port"] = "src" + str(percent_src_ports.keys()[0])
                else:
                    if debug: print "\n Using top dest port: ", percent_dst_ports.keys()[0]
                    df_pattern = df_filtered[df_filtered['dst_port'] == percent_dst_ports.keys()[0]]
                    result["selected_port"] = "dst" + str(percent_dst_ports.keys()[0])
            else:
                if debug: print 'no top source/dest port' 
                return None

            # Calculating the total number of packets involved in the attack
            pattern_packets = len(df_pattern)
            
            result["pattern_packet_count"] = pattern_packets

            # Calculating the percentage of the current pattern compared to the raw input file
            representativeness = float(pattern_packets) * 100 / float(total_packets_to_target)
            result["pattern_traffic_share"] = representativeness
            attack_label = 'In %.2f' % representativeness + "\n " + attack_label

            # Checking the existence of HTTP data
            http_data = df_pattern['http_data'].value_counts().divide(float(pattern_packets) / 100)

            # Checking the existence of TCP flags
            percent_tcp_flags = df_pattern['tcp_flag'].value_counts().divide(float(pattern_packets) / 100)

            # Calculating the number of source IPs involved in the attack
            ips_involved = df_pattern['src_ip'].unique()

            if len(ips_involved) < 2:
                
                if debug: print "\n###################################################################################################################"
                if debug: print "\n###################################################################################################################"
                if debug: print "\n###################################################################################################################"
                if debug: print("\nNO MORE PATTERNS")
                break
            
            if debug: print("\n############################\nPATTERN (ATTACK VECTOR) LABEL "+ "\n############################")
            
            attack_label = attack_label + "\n"+ str(len(ips_involved)) + " source IPs"
            result["src_ips"] = ips_involved.tolist()

            # Calculating the number of source IPs involved in the attack
            result["start_timestamp"] = df_pattern['timestamp'].min().item()
            result["end_timestamp"] = df_pattern['timestamp'].max().item()

            # Calculating the distribution of TTL variation (variation -> number of IPs)
            ttl_variations = df_pattern.groupby(['src_ip'])['ip_ttl'].agg(np.ptp).value_counts().sort_index()
            
            if debug: print('TTL variation : NR of source IPs')
            if debug: print(ttl_variations)
            
            ips_ttl_greater_4 = ttl_variations.groupby(np.where(ttl_variations.index > 4, '>4', ttl_variations.index)).sum()
            
#             if debug: print('\n IPs TTL variation >4')
#             if debug: print(ips_ttl_greater_4)
            
            result["ttl_variation"] = ttl_variations.to_dict()

            # Calculating the distribution of IP fragments (fragmented -> percentage of packets)
            percent_fragments = df_pattern['fragments'].value_counts().divide(float(pattern_packets) / 100)
            
            # Calculating the distribution of source ports that remains
            percent_src_ports = df_pattern['src_port'].value_counts().divide(float(pattern_packets) / 100)
            result["src_ports"] = percent_src_ports.to_dict()

            # Calculating the distribution of destination ports after the first filter
            percent_dst_ports = df_pattern['dst_port'].value_counts().divide(float(pattern_packets) / 100)
            result["dst_ports"] = percent_dst_ports.to_dict()

            # There are 3 possibilities of attacks cases!
            if (percent_src_ports.values[0] == 100):
                df_filtered = df_filtered[df_filtered['src_port'].isin(percent_src_ports.keys()) == False]
                if (len(percent_dst_ports) == 1):
                    # if debug: print("\nCASE 1: 1 source port to 1 destination port") if debug else next
                    port_label = "From " + portnumber2name(
                        percent_src_ports.keys()[0]) + "\n   - Against " + portnumber2name(
                        percent_dst_ports.keys()[0]) + "[" + '%.1f' % percent_dst_ports.values[0] + "%]"
                else:
                    # if debug: print("\nCASE 2: 1 source port to a set of destination ports") if debug else next
                    if (percent_dst_ports.values[0] >= 50):
                        port_label = "From " + portnumber2name(
                            percent_src_ports.keys()[0]) + "\n   - Against a set of (" + str(
                            len(percent_dst_ports)) + ") ports, such as " + portnumber2name(
                            percent_dst_ports.keys()[0]) + "[" + '%.2f' % percent_dst_ports.values[
                            0] + "%]" + " and " + portnumber2name(percent_dst_ports.keys()[1]) + "[" + '%.2f' % \
                                                                                                     percent_dst_ports.values[
                                                                                                         1] + "%]"
                    elif (percent_dst_ports.values[0] >= 33):
                        port_label = "From " + portnumber2name(
                            percent_src_ports.keys()[0]) + "\n   - Against a set of (" + str(
                            len(percent_dst_ports)) + ") ports, such as " + portnumber2name(
                            percent_dst_ports.keys()[0]) + "[" + '%.2f' % percent_dst_ports.values[
                            0] + "%]" + "; " + portnumber2name(percent_dst_ports.keys()[1]) + "[" + '%.2f' % \
                                                                                                  percent_dst_ports.values[
                                                                                                      1] + "%], and " + portnumber2name(
                            percent_dst_ports.keys()[2]) + "[" + '%.2f' % percent_dst_ports.values[2] + "%]"
                    else:
                        port_label = "From " + portnumber2name(
                            percent_src_ports.keys()[0]) + "\n   - Against a set of (" + str(
                            len(percent_dst_ports)) + ") ports, such as " + portnumber2name(
                            percent_dst_ports.keys()[0]) + "[" + '%.2f' % percent_dst_ports.values[
                            0] + "%]" + "; " + portnumber2name(percent_dst_ports.keys()[1]) + "[" + '%.2f' % \
                                                                                                  percent_dst_ports.values[
                                                                                                      1] + "%], and " + portnumber2name(
                            percent_dst_ports.keys()[2]) + "[" + '%.2f' % percent_dst_ports.values[2] + "%]"
            else:
                if (len(percent_src_ports) == 1):
                    df_filtered = df_filtered[df_filtered['src_port'].isin(percent_src_ports.keys()) == False]

                    # if debug: print("\nCASE 1: 1 source port to 1 destination port") if debug else next
                    port_label = "Using " + portnumber2name(percent_src_ports.keys()[0]) + "[" + '%.1f' %                                                                                                                   percent_src_ports.values[
                                                                                                                      0] + "%]" + "\n   - Against " + portnumber2name(
                        percent_dst_ports.keys()[0]) + "[" + '%.1f' % percent_dst_ports.values[0] + "%]"


                else:
                    # if debug: print("\nCASE 3: 1 source port to a set of destination ports") if debug else next
                    df_filtered = df_filtered[df_filtered['src_port'].isin(percent_src_ports.keys()) == False]

                    if (percent_src_ports.values[0] >= 50):
                        port_label = "From a set of (" + str(
                            len(percent_src_ports)) + ") ports, such as " + portnumber2name(
                            percent_src_ports.keys()[0]) + "[" + '%.2f' % percent_src_ports.values[
                            0] + "%] and " + portnumber2name(percent_src_ports.keys()[1]) + "[" + '%.2f' % \
                                                                                                percent_src_ports.values[
                                                                                                    1] + "%]" + "\n   - Against " + portnumber2name(
                            percent_dst_ports.keys()[0]) + "[" + '%.1f' % percent_dst_ports.values[0] + "%]"
                    elif (percent_src_ports.values[0] >= 33):
                        port_label = "From a set of (" + str(
                            len(percent_src_ports)) + ") ports, such as " + portnumber2name(
                            percent_src_ports.keys()[0]) + "[" + '%.2f' % percent_src_ports.values[
                            0] + "%], " + portnumber2name(percent_src_ports.keys()[1]) + "[" + '%.2f' % \
                                                                                             percent_src_ports.values[
                                                                                                 1] + "%], and " + portnumber2name(
                            percent_src_ports.keys()[2]) + "[" + '%.2f' % percent_src_ports.values[
                            2] + "%]" + "\n   - Against " + portnumber2name(percent_dst_ports.keys()[0]) + "[" + '%.1f' % \
                                                                                                            percent_dst_ports.values[
                                                                                                                0] + "%]"
                    else:
                        df_filtered = df_filtered[df_filtered['dst_port'].isin(percent_dst_ports.keys()) == False]
                        port_label = "From a set of (" + str(
                            len(percent_src_ports)) + ") ports, such as " + portnumber2name(
                            percent_src_ports.keys()[0]) + "[" + '%.2f' % percent_src_ports.values[
                            0] + "%], " + portnumber2name(percent_src_ports.keys()[1]) + "[" + '%.2f' % \
                                                                                             percent_src_ports.values[
                                                                                                 1] + "%], " + portnumber2name(
                            percent_src_ports.keys()[2]) + "[" + '%.2f' % percent_src_ports.values[
                            2] + "%]" + "; and " + portnumber2name(percent_src_ports.keys()[3]) + "[" + '%.2f' % \
                                                                                                      percent_src_ports.values[
                                                                                                          3] + "%]" + "\n   - Against " + portnumber2name(
                            percent_dst_ports.keys()[0]) + "[" + '%.1f' % percent_dst_ports.values[0] + "%]"

                                
            # Testing HTTP request
            #if len(http_data) > 0 and ((percent_dst_ports.index[0] == 80) or (percent_dst_ports.index[0] == 443)):            
            if len(http_data) > 0 :
                attack_label = attack_label + "; " + http_data.index[0]

            # Testing TCP flags
            if (len(percent_tcp_flags) > 0) and (percent_tcp_flags.values[0] > 50):
                attack_label = attack_label + "; TCP flags: " + tcpflagletters2names(
                    percent_tcp_flags.index[0]) + "[" + '%.1f' % percent_tcp_flags.values[0] + "%]"

            # IP fragmentation
            if '1' in percent_fragments.keys():
                if (percent_fragments['1'] > 0.3):
                    fragment_label = "%.2f" % percent_fragments['1'] + "packets with fragments marked"
                    result["fragmented"] = True

            # IP spoofing (if (more than 0) src IPs had the variation of the ttl higher than a treshold)
            if '>4' in ips_ttl_greater_4.keys():
                if (ips_ttl_greater_4['>4'] > len(ips_involved)*0.1 ):
                    result["spoofed"]=True
                    spoofed_label = "Likely involving spoofed IPs"
                else:
                    # Involved in 
                    # Reflection and Amplification
                    ##!!!! include the possibility to check top src_ips open port (censys) 
                    if percent_src_ports.values[0] >= 1:
                        result["reflected"]=True
                        reflection_label = "Reflection & Amplification"

            print "\nSUMMARY:\n"                    +"- %.2f" % representativeness +"% of the packets targeting "+top_dst_ip+"\n"                    +"   - Involved "+str(len(ips_involved))+" source IP addresses\n"                    +"   - Using IP protocol "+protocolnumber2name(top_ip_proto)+"\n"                    +"   - "+port_label+"\n"                    +"   - "+fragment_label                    +"   - "+reflection_label                    +"   - "+spoofed_label
            
            allpatterns["patterns"].append(result)


    return allpatterns

